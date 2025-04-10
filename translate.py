import os
import json
from pathlib import Path
from typing import Optional, List, Tuple
import jinja2
import re
from dotenv import load_dotenv
import time
import logging

load_dotenv()
MAX_RETRIES = 5
RETRY_DELAY = 5
MAX_CHUNK_SIZE = 500
INITIAL_CHUNK_LINES = 100

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class TranslationProcessor:
    def __init__(self, input_file: str):
        self.input_file = input_file
        self.template_loader = jinja2.FileSystemLoader(searchpath="templates")
        self.template_env = jinja2.Environment(loader=self.template_loader)
        self.successful_chunks = []
        self.original_line_count = 0
        self.original_content = ""
        self.source, self.bookid, self.index = self.parse_filename(input_file)
        self.generated_file = None

    def parse_filename(self, filename: str) -> tuple[str, str, str]:
        parts = Path(filename).stem.split('-')
        return parts[0], parts[1], parts[2]
    
    def get_template(self) -> jinja2.Template:
        templates_to_try = [
            f"{self.source}-{self.bookid}.html",
            f"{self.source}.html",
            "default.html"
        ]
        for template_name in templates_to_try:
            try:
                return self.template_env.get_template(template_name)
            except jinja2.exceptions.TemplateNotFound:
                continue
        raise RuntimeError("No valid template found")

    def split_content(self, content: str) -> List[Tuple[str, List[int]]]:
        lines = content.split('\n')
        self.original_line_count = len(lines)
        self.original_content = content
        return [
            ('\n'.join(lines[i:i + INITIAL_CHUNK_LINES]), [i // INITIAL_CHUNK_LINES + 1])
            for i in range(0, len(lines), INITIAL_CHUNK_LINES)
        ]
    
    def split_chunk(self, chunk: str, indices: List[int]) -> List[Tuple[str, List[int]]]:
        lines = chunk.split('\n')
        mid = len(lines) // 2
        return [
            ('\n'.join(lines[:mid]), indices + [1]),
            ('\n'.join(lines[mid:]), indices + [2])
        ]
    
    def translate_chunk(self, chunk: str, retry_count: int = 0) -> Optional[str]:
        llm_model = os.environ.get('LLM_MODEL')
        llm_prompt = os.environ.get('LLM_PROMPT')
        llm_token = os.environ.get('LLM_TOKEN')
        llm_url = os.environ.get('LLM_URL')

        if not all([llm_model, llm_prompt, llm_token, llm_url]):
            logging.error("Missing LLM configuration")
            return None

        import requests
        headers = {'Authorization': f'Bearer {llm_token}', 'Content-Type': 'application/json'}
        data = {
            "model": llm_model,
            "messages": [{"role": "user", "content": f"{llm_prompt}\n\n{chunk}"}],
            "stream": False,
        }

        try:
            response = requests.post(f"{llm_url.rstrip('/')}/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            translated = response.json()['choices'][0]['message']['content']
            
            if not translated.strip():
                raise ValueError("Received empty translation")
                
            return translated
        except Exception as e:
            if retry_count < MAX_RETRIES:
                logging.warning(f"Retrying chunk (attempt {retry_count + 1}): {e}")
                time.sleep(RETRY_DELAY)
                return self.translate_chunk(chunk, retry_count + 1)
            logging.error(f"Final translation failure: {e}")
            return None
    
    def process_chunk(self, chunk: str, indices: List[int]) -> bool:
        translated = self.translate_chunk(chunk)
        if translated:
            self.successful_chunks.append((indices, translated))
            return True

        if len(chunk) < MAX_CHUNK_SIZE:
            logging.error(f"Failed to translate minimum-size chunk: {indices}")
            return False

        sub_chunks = self.split_chunk(chunk, indices)
        for sub_chunk, sub_indices in sub_chunks:
            if not self.process_chunk(sub_chunk, sub_indices):
                return False
        return True
    
    def save_debug_files(self, original: str, translated: str):
        debug_dir = Path("test")
        debug_dir.mkdir(exist_ok=True)
        timestamp = int(time.time())
        filestem = Path(self.input_file).stem
        
        original_path = debug_dir / f"original_{filestem}_{timestamp}.txt"
        translated_path = debug_dir / f"translated_{filestem}_{timestamp}.txt"
        
        original_path.write_text(original, encoding="utf-8")
        translated_path.write_text(translated, encoding="utf-8")
        logging.info(f"Debug files saved: {original_path}, {translated_path}")

    def validate_completion(self) -> bool:
        sorted_chunks = sorted(self.successful_chunks, key=lambda x: x[0])
        translated_content = '\n'.join([chunk for _, chunk in sorted_chunks])
        translated_lines = len(translated_content.split('\n'))
        
        if translated_lines != self.original_line_count:
            self.save_debug_files(self.original_content, translated_content)
            allowed_diff = int(0.1 * self.original_line_count)
            
            if abs(translated_lines - self.original_line_count) > allowed_diff:
                logging.error(f"Line count difference >10%: Original {self.original_line_count} vs {translated_lines}")
                return False
            logging.warning(f"Line count difference within 10%: {self.original_line_count} vs {translated_lines}")
        return True

    def process_file(self) -> Optional[str]:
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.original_content = data['content']

        chunks = self.split_content(data['content'])
        for chunk, indices in chunks:
            if not self.process_chunk(chunk, indices):
                logging.error("Aborting due to failed chunk")
                return None

        if not self.validate_completion():
            logging.error("Content validation failed")
            return None

        book_dir = Path(re.sub(r'[^\w_\-]', '_', data['book']))
        book_dir.mkdir(parents=True, exist_ok=True)
        
        sorted_chunks = [chunk for _, chunk in sorted(self.successful_chunks, key=lambda x: x[0])]
        template = self.get_template()
        rendered = template.render(
            title=data['title'],
            content=''.join(f'<p>{line}</p>' for line in "\n".join(sorted_chunks).split("\n")),
            url=data['url'],
            source=data['source'],
            index=int(self.index),
            book=data['book']
        )
        
        self.generated_file = book_dir / f"{int(self.index):04d}.html"
        with open(self.generated_file, 'w', encoding='utf-8') as f:
            f.write(rendered)
        
        return str(self.generated_file)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python translate.py <input_file>")
        sys.exit(1)

    processor = TranslationProcessor(sys.argv[1])
    result = processor.process_file()
    if result:
        print(f"GENERATED_FILE:{result}")
        sys.exit(0)
    else:
        sys.exit(1)
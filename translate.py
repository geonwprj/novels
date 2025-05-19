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
INITIAL_CHUNK_LINES = 50

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
        llm_provider = os.environ.get('LLM_PROVIDER')

        if not all([llm_model, llm_prompt, llm_token, llm_url]):
            logging.error("Missing LLM configuration")
            return None

        import requests

        if llm_provider == 'gemini':
            headers = {'Content-Type': 'application/json'}
            data = {
                    "contents": [
                    {
                        "parts": [
                        {
                            "text": f"{llm_prompt}\n\n{chunk}"
                        }
                        ]
                    }
                    ]
                }
            url = f"{llm_url.rstrip('/')}/v1beta/models/{llm_model}:generateContent?key={llm_token}"
        else:
            headers = {'Authorization': f'Bearer {llm_token}', 'Content-Type': 'application/json'}
            data = {
                "model": llm_model,
                "messages": [{"role": "user", "content": f"{llm_prompt}\n\n{chunk}"}],
                "stream": False,
            }
            url = f"{llm_url.rstrip('/')}/chat/completions"

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            if llm_provider == 'gemini':
    #               "candidates": [
    # {
    #   "content": {
    #     "parts": [
    #       {
    #         "text":
                translated = response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
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

        # Count non-empty lines and characters in original and translated content
        original_non_empty_lines = sum(1 for line in self.original_content.split('\n') if line.strip())
        translated_non_empty_lines = sum(1 for line in translated_content.split('\n') if line.strip())
        original_char_count = len(self.original_content)
        translated_char_count = len(translated_content)

        line_diff_within_tolerance = True
        if original_non_empty_lines != translated_non_empty_lines:
            allowed_line_diff = max(1, int(0.1 * original_non_empty_lines)) # Ensure at least 1 line tolerance for small files
            if abs(translated_non_empty_lines - original_non_empty_lines) > allowed_line_diff and abs(translated_non_empty_lines - original_non_empty_lines) > 15:
                line_diff_within_tolerance = False
                logging.warning(f"Non-empty line difference outside 10% tolerance: Original {original_non_empty_lines} vs Translated {translated_non_empty_lines}")
            else:
                 logging.warning(f"Non-empty line difference within 10% tolerance: {original_non_empty_lines} vs {translated_non_empty_lines}")

        char_diff_within_tolerance = True
        if not line_diff_within_tolerance:
            if original_char_count != translated_char_count:
                allowed_char_diff = int(0.1 * original_char_count)
                if abs(translated_char_count - original_char_count) > allowed_char_diff:
                    char_diff_within_tolerance = False
                    logging.warning(f"Character count difference outside 10% tolerance: Original {original_char_count} vs Translated {translated_char_count}")
                else:
                    logging.warning(f"Character count difference within 10% tolerance: {original_char_count} vs {translated_char_count}")

        if not line_diff_within_tolerance and not char_diff_within_tolerance:
            self.save_debug_files(self.original_content, translated_content)
            logging.error("Content validation failed: Both line count and character count differences are outside tolerance.")
            return False

        logging.info("Content validation passed.")
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
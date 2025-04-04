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
RETRY_DELAY = 5  # seconds between retries
MAX_CHUNK_SIZE = 500  # characters
INITIAL_CHUNK_LINES = 100  # lines per initial chunk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class TranslationProcessor:
    """Handles the translation of JSON files"""
    
    def __init__(self, input_file: str):
        self.input_file = input_file
        self.template_loader = jinja2.FileSystemLoader(searchpath="templates")
        self.template_env = jinja2.Environment(loader=self.template_loader)
        self.successful_chunks = []
        self.failed_chunks = []
        
        # Parse input filename
        self.source, self.bookid, self.index = self.parse_filename(input_file)
        
    def parse_filename(self, filename: str) -> tuple[str, str, str]:
        """Extract source, bookid, and index from filename"""
        parts = Path(filename).stem.split('-')
        return parts[0], parts[1], parts[2]
    
    def get_template(self) -> jinja2.Template:
        """Find appropriate template with fallback logic"""
        # Try source-bookid template
        template_name = f"{self.source}-{self.bookid}.html"
        try:
            return self.template_env.get_template(template_name)
        except jinja2.exceptions.TemplateNotFound:
            pass  # Template not found, try next
        
        # Try source template
        template_name = f"{self.source}.html"
        try:
            return self.template_env.get_template(template_name)
        except jinja2.exceptions.TemplateNotFound:
            pass  # Template not found, fallback to default
        
        # Fallback to default
        logging.info("Using default template: default.html")
        return self.template_env.get_template("default.html")
    
    def split_content(self, content: str) -> List[Tuple[str, List[int]]]:
        """Split content into initial chunks of 100 lines each"""
        lines = content.split('\n')
        chunks = []
        for i in range(0, len(lines), INITIAL_CHUNK_LINES):
            chunk = '\n'.join(lines[i:i + INITIAL_CHUNK_LINES])
            chunks.append((chunk, [i // INITIAL_CHUNK_LINES + 1]))
        return chunks
    
    def split_chunk(self, chunk: str, indices: List[int]) -> List[Tuple[str, List[int]]]:
        """Split a chunk into two halves"""
        lines = chunk.split('\n')
        mid = len(lines) // 2
        return [
            ('\n'.join(lines[:mid]), indices + [1]),
            ('\n'.join(lines[mid:]), indices + [2])
        ]
    
    def translate_chunk(self, chunk: str, retry_count: int = 0) -> Optional[str]:
        """Translate a single chunk of text"""
        llm_model = os.environ.get('LLM_MODEL')
        llm_prompt = os.environ.get('LLM_PROMPT')
        llm_token = os.environ.get('LLM_TOKEN')
        llm_url = os.environ.get('LLM_URL')

        if not all([llm_model, llm_prompt, llm_token, llm_url]):
            logging.error("Missing required LLM configuration in environment variables")
            return None

        import requests
        headers = {
            'Authorization': f'Bearer {llm_token}',
            'Content-Type': 'application/json'
        }
        data = {
            "model": llm_model,
            "messages": [{"role": "user", "content": f"{llm_prompt}\n\n{chunk}"}],
            "stream": False,
        }
        try:
            logging.info(f"Processing...Chunk size: {len(chunk)}")
            response = requests.post(f"{llm_url.rstrip('/')}/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            translated_text = response.json()['choices'][0]['message']['content']
            return translated_text
        except requests.exceptions.RequestException as e:
            logging.error(f"Translation request failed (attempt {retry_count + 1}/{MAX_RETRIES}): {e}")
            if retry_count < MAX_RETRIES and len(chunk) < MAX_CHUNK_SIZE:
                time.sleep(RETRY_DELAY)
                return self.translate_chunk(chunk, retry_count + 1)
            return None
    
    def process_chunk(self, chunk: str, indices: List[int]) -> bool:
        """Process a chunk with recursive splitting if needed"""
        translated = self.translate_chunk(chunk)
        if translated:
            self.successful_chunks.append(translated)
            return True
        
        if len(chunk) < MAX_CHUNK_SIZE:
            logging.error(f"Failed to translate small chunk: {indices}")
            return False
        
        logging.info(f"Splitting failed chunk: {indices}")
        sub_chunks = self.split_chunk(chunk, indices)
        for sub_chunk, sub_indices in sub_chunks:
            if not self.process_chunk(sub_chunk, sub_indices):
                return False
        return True
    
    def process_file(self):
        """Process the entire file"""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        chunks = self.split_content(data['content'])

        
        for chunk, indices in chunks:
            logging.info(f"Processing: indices: {indices}, totel chunks: {len(chunks)}")
            if not self.process_chunk(chunk, indices):
                logging.error("Translation failed due to unrecoverable error")
                return False
        
        if self.successful_chunks:
            # Book directory path
            book_dir_name = re.sub(r'[^\w_\-]', '_', data['book'])
            output_dir = Path(book_dir_name)
            logging.info(f"Creating output directory: {output_dir}")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Render template
            template = self.get_template()
            rendered = template.render(
                title=data['title'],
                content=''.join([f'<p>{line}</p>' for line in "\n".join(self.successful_chunks).split("\n")]),
                url=data['url'],
                source=data['source'],
                index=int(self.index),
                book=data['book']
            )
            
            # Write output file
            output_file = Path(book_dir_name) / f"{int(self.index):04d}.html"
            logging.info(f"Writing output file: {output_file}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rendered)
        
        return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python translate.py <input_file>")
        sys.exit(1)
    
    processor = TranslationProcessor(sys.argv[1])
    success = processor.process_file()
    
    if not success:
        logging.error("Translation failed")
    sys.exit(0 if success else 1)
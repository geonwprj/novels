import os
import json
from pathlib import Path
from typing import Optional
import jinja2
import re
from dotenv import load_dotenv

load_dotenv()
CHUNK_LINES = 100
MAX_RETRIES = 5

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
        print("Using default template: default.html")  # LOGGING
        return self.template_env.get_template("default.html") # Load default template by name
        # return self.template_env.get_template("templates/default.html") # Try loading with explicit path - previous attempt, might not work with FileSystemLoader
    
    def split_content(self, content: str) -> list[str]:
        """Split content into chunks of CHUNK_LINES lines"""
        lines = content.split('\n')
        return ['\n'.join(lines[i:i + CHUNK_LINES]) 
                for i in range(0, len(lines), CHUNK_LINES)]
    
    def translate_chunk(self, chunk: str, retry_count: int = 0) -> Optional[str]:
        """Translate a single chunk of text"""
        llm_model = os.environ.get('LLM_MODEL')
        llm_prompt = os.environ.get('LLM_PROMPT')
        llm_token = os.environ.get('LLM_TOKEN')
        llm_url = os.environ.get('LLM_URL')
        # print(f"LLM_MODEL: {llm_model}")
        # print(f"LLM_PROMPT: {llm_prompt}")
        # print(f"LLM_TOKEN: {llm_token}")
        # print(f"LLM_URL: {llm_url}")
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
            response = requests.post(f"{llm_url.rstrip('/')}/chat/completions", headers=headers, json=data)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            translated_text = response.json()['choices'][0]['message']['content']
            return translated_text
        except requests.exceptions.RequestException as e:
            print(f"Translation request failed: {e}")
            if retry_count < MAX_RETRIES:
                return self.translate_chunk(chunk, retry_count + 1)
            return None
    
    def process_file(self):
        """Process the entire file"""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        chunks = self.split_content(data['content'])
        
        for i, chunk in enumerate(chunks):
            translated = self.translate_chunk(chunk)
            if translated:
                self.successful_chunks.append(translated)
            else:
                self.failed_chunks.append(i + 1)  # 1-based chunk numbering
        
        if self.successful_chunks:
            # Book directory path
            book_dir_name = re.sub(r'[^\w_\-]', '_', data['book'])  # Sanitize book name
            output_dir = Path(book_dir_name)
            print(f"Creating output directory: {output_dir}") # LOGGING
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Render template
            template = self.get_template()
            rendered = template.render(
                title=data['title'],
                content=''.join([f'<p>{line}</p>' for line in "\n".join(self.successful_chunks).split("\n")]),
                url=data['url'],
                source=data['source'],
                index=int(self.index), # Pass index to template context
                book=data['book'] # Pass book to template context
            )
            
            # Write output file directly in book dir
            output_file = Path(book_dir_name) / f"{int(self.index):04d}.html" # Output file path
            print(f"Writing output file: {output_file}") # LOGGING
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rendered)
        return f"{str(output_file)} {str(len(self.failed_chunks) == 0)}"
        return str(output_file), len(self.failed_chunks) == 0

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python translate.py <input_file>")
        sys.exit(1)
    
    processor = TranslationProcessor(sys.argv[1])
    success = processor.process_file()
    
    if not success:
        print(f"Warning: Failed to translate chunks: {processor.failed_chunks}")
    sys.exit(0 if success else 1)
# Translation Processing System

This project automatically processes text files for translation using LLM technology.

## How It Works

1. Place JSON files containing text content in the `processing` directory.
2. The `translate.py` script will:
   - Read configuration from environment variables.
   - Split the text content into manageable chunks.
   - Process each chunk through the translation system using an LLM API.
   - Retry failed chunks up to 5 times.
   - Combine successful translations into an HTML file.
3. The processed HTML file will be saved in a directory named after the book title, with the index number as the filename (e.g., `Book_Title/0001.html`).

## Requirements

- Python 3.10+
- `requests` library
- `jinja2` library
- `python-dotenv` library
- An LLM API endpoint (e.g., OpenAI-like)

## Usage

1. Add JSON files to the `processing` directory. Ensure each JSON file has the following structure:
   ```json
   {
     "bookid": "your_book_id",
     "book": "Book Title in Chinese",
     "source": "source_name",
     "title": "Chapter Title",
     "url": "source_url",
     "content": "Text content to be translated"
   }
   ```
2. Run the `translate.py` script, providing the input JSON file path as an argument in your GitHub Actions workflow:
   ```bash
   python translate.py processing/your_input_file.json
   ```
3. Check for the generated HTML files in the newly created book directory after the workflow run.

## Notes

- The translation process uses an LLM API specified by `LLM_URL`, `LLM_MODEL`, `LLM_PROMPT`, and `LLM_TOKEN` environment variables, configured in your GitHub Actions workflow.
- Files should be in UTF-8 encoding.
- Maximum retry attempts per chunk: 5.
- The output HTML uses `<p>` tags for line breaks within paragraphs.
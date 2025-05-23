# src/translate.py
import json
import os
import sys
import time
import math # Import math for ceil/floor if needed for percentage check

def split_content(text, max_length=200):
    """
    Splits the text into exactly two parts based on specific delimiters and maximum length.

    Args:
        text (str): The text to split.
        max_length (int): The maximum length of each part.

    Returns:
        list of str: The split parts of the text.
    """
    if len(text) <= max_length:
        return [text]

    # 1. Attempt to split by newline
    if '\n' in text:
        # Find the position of the last newline before half of the text
        half_length = len(text) // 2
        last_newline = text.rfind('\n', 0, half_length)
        if last_newline != -1:
            part1 = text[:last_newline]
            part2 = text[last_newline + 1:]
            return [part1, part2]
        else:
            # No newline in the first half, split at max_length
            return [text[:max_length], text[max_length:]]

    # 2. If no newline, attempt to split by '。'
    if '。' in text:
        # Find the position of the last '。' before half of the text
        half_length = len(text) // 2
        last_stop = text.rfind('。', 0, half_length)
        if last_stop != -1:
            part1 = text[:last_stop + 1]  # Include the '。'
            part2 = text[last_stop + 1:]
            return [part1, part2]
        else:
            # No '。' in the first half, split at max_length
            return [text[:max_length], text[max_length:]]

    # 3. Fallback: Split by character length
    return [text[:max_length], text[max_length:]]

# Assume the LLM utility is in src/utils/llm.py
# and has a class/function capable of making translation calls.
# We'll assume an LLM class is passed to __init__ with a method like `translate_text`.
# The LLM class should handle the actual API interaction and potential exceptions.
# For demonstration, we'll assume the LLM object has a method `translate(prompt, text)`
# which returns the translated text or raises an exception/returns a specific error indicator.

# Define a placeholder for the LLM class if it's not fully implemented yet
# In a real scenario, you would import your actual LLM class here.
# Example import if your LLM class is in src/utils/llm.py:
# from src.utils.llm import YourActualLLMClass

class Translate:
    def __init__(self, llm, system_prompt):
        """
        Initializes the Translate class with an LLM object and a system prompt.

        Args:
            llm: An object representing the Language Model, expected to have a
                 `translate(prompt, text)` method.
            system_prompt: The system prompt to use for translation.
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.template_path = 'templates/default.html' # Assuming template is here

        if not os.path.exists(self.template_path):
             print(f"Error: HTML template not found at {self.template_path}", file=sys.stderr)
             # Decide how to handle this - maybe raise an exception or exit
             # For now, we'll let it fail later when saving
             pass


    def validate_result(self, original_content, translated_content):
        """
        Validates the translated content against the original content.

        Checks if character count and line count variance is within 10%.
        Character count is checked only if line count check is fail.

        Args:
            original_content: The original text content (string).
            translated_content: The translated text content (string).

        Returns:
            True if validation passes, False otherwise.
        """
        original_lines = original_content.strip().split('\n')
        translated_lines = translated_content.strip().split('\n')

        original_line_count = len(original_lines)
        translated_line_count = len(translated_lines)

        # Check line count variance
        line_count_variance_too_high = False
        if original_line_count > 0:
            line_variance = abs(original_line_count - translated_line_count) / original_line_count
            if line_variance > 0.10: # More than 10% variance
                print(f"Validation failed: Line count variance too high ({line_variance:.2f}). Original: {original_line_count}, Translated: {translated_line_count}", file=sys.stderr)
                line_count_variance_too_high = True
        elif translated_line_count > 0:
             # Original had no lines, but translated does. This is likely an issue.
             print("Validation failed: Original content had no lines, but translated content does.", file=sys.stderr)
             return False


        # Check character count only if line count check failed significantly
        if line_count_variance_too_high:
            original_char_count = len(original_content)
            translated_char_count = len(translated_content)
            if original_char_count > 0:
                 char_variance = abs(original_char_count - translated_char_count) / original_char_count
                 if char_variance > 0.10:
                     print(f"Validation failed: Character count variance too high ({char_variance:.2f}). Original: {original_char_count}, Translated: {translated_char_count}", file=sys.stderr)
                     return False
                 else:
                     print(f"Validation Warning: Line count variance high, but character count variance ({char_variance:.2f}) is acceptable.", file=sys.stderr)
                     # Based on the prompt, if char count is okay despite line count, it passes.
                     return True
            elif translated_char_count > 0:
                 # Original had no chars, but translated does. This is likely an issue.
                 print("Validation failed: Original content had no characters, but translated content does.", file=sys.stderr)
                 return False
            else:
                 # Both original and translated had no characters. Valid.
                 return True
        else:
            # Line count variance was within 10%, validation passes based on line count.
            return True


    def extract_content(self, json_path):
        """
        Extracts content and metadata from a JSON file.

        Args:
            json_path: Path to the input JSON file.

        Returns:
            A dictionary containing 'book', 'index', 'title', and 'content',
            or None if the file cannot be read or parsed.
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Extract required fields
                content_data = {
                    'book': data.get('book'),
                    'index': data.get('index'),
                    'title': data.get('title'),
                    'content': data.get('content')
                }
                # Basic check if essential fields are present
                if not all([content_data['book'], content_data['index'] is not None, content_data['title'], content_data['content']]):
                     print(f"Error: Missing essential fields in JSON file {json_path}", file=sys.stderr)
                     return None
                return content_data
        except FileNotFoundError:
            print(f"Error: JSON file not found at {json_path}", file=sys.stderr)
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {json_path}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"An unexpected error occurred while reading {json_path}: {e}", file=sys.stderr)
            return None

    def translate_content(self, content):
        """
        Translates content using the LLM, handling errors and splitting if needed.

        Args:
            content (str): The text content to translate.

        Returns:
            str or None: The translated text, or None if translation fails after retries.
        """
        max_retries = 3
        retry_delay = 5  # seconds

        def call_llm(text_to_translate):
            """
            Helper function to call the LLM and handle specific errors.

            Args:
                text_to_translate (str): The text to translate.

            Returns:
                tuple: (error_code or None, translated_text or None)
            """
            try:
                html_rtn, translated_text = self.llm.run(sysprompt=self.system_prompt, userprompt=text_to_translate)
                # print(f"LLM html error response: {html_rtn}", file=sys.stderr)
                if ((html_rtn is None) and (translated_text is not None)):
                    return None, translated_text  # No error, return translated text
                # Check for short response indicating connection error
                if translated_text is not None and len(translated_text) < 200 and len(text_to_translate) > 200:
                    print(f"Warning: Short response ({len(translated_text)} chars) for long input ({len(text_to_translate)} chars). Treating as connection error.", file=sys.stderr)
                    return "CONNECTION_ERROR", None
                # Check for specific error indicators from LLM
                if (("TOKEN_EXCEEDED" in html_rtn) or ("HTML error 500" in html_rtn) or ("HTML error 504" in html_rtn)):
                    print("Warning: LLM returned HTML error 500/504.", file=sys.stderr)
                    return "TOKEN_EXCEEDED", None
                return None, translated_text  # Success
            except Exception as e:
                # Catch other potential exceptions from the LLM call
                print(f"Error during LLM call: {e}", file=sys.stderr)
                if "504 Server Error:".lower() in str(e).lower():
                    print("Error message indicates token limit.", file=sys.stderr)
                    return "TOKEN_EXCEEDED", None
                else:
                    return "OTHER_ERROR", None  # Indicate a different type of error

        def translate_recursive(text, retries_remaining):
            """
            Recursively attempts to translate the text, handling retries and splitting.

            Args:
                text (str): The text to translate.
                retries_remaining (int): The number of retries left.

            Returns:
                str or None: The translated text or None if failed.
            """
            print(f"len(text): {len(text)}, lines: {len(text.splitlines())}", file=sys.stderr)
            error, result = call_llm(text)
            if error == "TOKEN_EXCEEDED":
                print("Token limit exceeded. Splitting content and retrying parts.", file=sys.stderr)
                parts = split_content(text)
                translated_parts = []
                for i, part in enumerate(parts):
                    if not part.strip():
                        translated_parts.append("")
                        continue
                    translated_part = translate_recursive(part, max_retries)
                    if translated_part is None:
                        print(f"Failed to translate part {i+1}/{len(parts)} after retries.", file=sys.stderr)
                        return None  # Fail the whole translation if any part fails
                    translated_parts.append(translated_part)
                return "\n".join(translated_parts)
            elif error in ["CONNECTION_ERROR", "OTHER_ERROR"]:
                if retries_remaining > 0:
                    print(f"Translation failed ({error}). Retrying whole content ({retries_remaining} retries left).", file=sys.stderr)
                    time.sleep(retry_delay)
                    return translate_recursive(text, retries_remaining - 1)
                else:
                    print(f"Failed to translate content after {max_retries} retries.", file=sys.stderr)
                    return None  # Translation failed after all retries
            else:
                if result is None:
                    return None
                else:
                    return result  # Initial translation successful

        return translate_recursive(content, max_retries)

    def save_html(self, book, index, title, content):
        """
        Saves the translated content into an HTML file using a template.

        Args:
            book: The book title.
            index: The chapter index (integer).
            title: The chapter title.
            content: The translated HTML content (can contain <p> tags etc.).

        Returns:
            The path to the saved HTML file on success, None on failure.
        """
        output_dir = os.path.join('.', book) # Output directory is ./book
        os.makedirs(output_dir, exist_ok=True) # Create directory if it doesn't exist

        # Format index as 4 digits
        formatted_index = f"{index:04d}"
        output_filename = f"{formatted_index}.html"
        output_path = os.path.join(output_dir, output_filename)

        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            # Replace placeholders in the template
            # Basic string replacement - consider Jinja2 for more complex templates
            html_content = template_content.replace('{{book}}', str(book))
            html_content = html_content.replace('{{title}}', str(title))
            # Replace <p></p>{{content}} with just {{content}} if content already has tags
            # Or wrap content in <p> tags if it's plain text.
            # Assuming content might contain paragraphs already, let's just replace {{content}}
            # and adjust the template slightly if needed. The template has <p></p>{{content}}
            # which might result in an empty paragraph before the content. Let's fix that in the template reading.
            # A better approach is to split content by \n and wrap each line in <p>
            processed_content = "".join([f"<p>{line}</p>" for line in content.split('\n') if line.strip()])

            html_content = html_content.replace('<p></p>{{content}}', processed_content) # Replace the specific template part
            # Also replace the next chapter link placeholder
            html_content = html_content.replace("{{ '%04d' % (index + 1) }}", f"{(index + 1):04d}")


            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"Successfully saved HTML to {output_path}", file=sys.stderr)
            return output_path

        except FileNotFoundError:
            print(f"Error: HTML template not found at {self.template_path}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"An error occurred while saving HTML to {output_path}: {e}", file=sys.stderr)
            return None

    def run(self, json_path):
        """
        Orchestrates the translation process for a single JSON file.

        Args:
            json_path: Path to the input JSON file.

        Returns:
            The path to the generated HTML file on success, None on failure.
        """
        print(f"Starting processing for {json_path}", file=sys.stderr)

        # 1. Extract content
        content_data = self.extract_content(json_path)
        if content_data is None:
            print(f"Failed to extract content from {json_path}", file=sys.stderr)
            return None

        original_content = content_data['content']
        book = content_data['book']
        index = content_data['index']
        title = content_data['title']

        # 2. Translate content
        translated_content = self.translate_content(original_content)
        if translated_content is None:
            print(f"Failed to translate content for {json_path}", file=sys.stderr)
            return None

        # 3. Validate result
        if not self.validate_result(original_content, translated_content):
            print(f"Validation failed for translated content from {json_path}", file=sys.stderr)
            # Decide if you want to save the potentially bad translation or not
            # For now, let's return None if validation fails.
            return None

        # 4. Save HTML
        output_html_path = self.save_html(book, index, title, translated_content)
        if output_html_path is None:
            print(f"Failed to save HTML for {json_path}", file=sys.stderr)
            return None

        print(f"Successfully processed {json_path}. Output: {output_html_path}", file=sys.stderr)
        return output_html_path

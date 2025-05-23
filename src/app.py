# src/app.py
import sys
import argparse
import os
from dotenv import load_dotenv
from utils import Llm, Translate

# --- Step 1: Load environment variables from .env file ---
# Assuming the .env file is in the project root directory (one level up from src)
# We need to find the project root. A common way is to look for a marker file
# like .env itself, or requirements.txt, or .git.
# For simplicity here, we'll assume the script is run from the project root
# or that the .env file is directly accessible relative to the script's location.
# A more robust way might involve finding the project root dynamically.
# Let's assume .env is one directory up from src/app.py
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}. Ensure API keys are set in your environment.")

# Now you can access environment variables using os.environ.get() or os.getenv()
# The Llm class automatically reads these using os.environ.get()


# --- Step 2: Call the LLM as a sample ---

def main():
    """
    Entry point for processing novel translation from a JSON file.
    """
    if len(sys.argv) != 2:
        print("Usage: python src/app.py <input_file>")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Process novel content from a JSON file and generate HTML.")
    parser.add_argument("input_json_path", help="Path to the input JSON file containing novel content.")

    args = parser.parse_args()

    input_path = args.input_json_path

    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}", file=sys.stderr)
        sys.exit(1)

    # Call the function that does the actual processing and HTML generation
    # This function should take the input_path and return the path to the generated HTML file
    # or None/False if an error occurred during processing.
    print(f"Processing input file: {input_path}", file=sys.stderr)
    result_html_path = process_novel_translation(input_path)

    # result_html_path = None  # Placeholder for the actual processing function

    if result_html_path and os.path.exists(result_html_path):
        print(f"GENERATED_FILE:{result_html_path}")
        sys.exit(0)
    else:
        print(f"Error: Processing failed or output file not generated for {input_path}", file=sys.stderr)
        sys.exit(1)


def process_novel_translation(input_path):
    llmprovider = os.getenv('LLM_PROVIDER', 'gemini')
    llmtoken = os.getenv('LLM_TOKEN', None)
    llmurl = os.getenv('LLM_URL', None)
    llmmodel = os.getenv('LLM_MODEL', None)
    llmsys = os.getenv('LLM_PROMPT', None)

    # Example 1: Using Gemini (default provider)
    llm = Llm(provider=llmprovider, url=llmurl, token=llmtoken, model=llmmodel) # Uses GEMINI_API_KEY from environment

    # Create a Translate instance
    translator = Translate(llm, llmsys)

    # Run the process with the sample file
    print("\n--- Running translation process with sample file ---", file=sys.stderr)
    output_file = translator.run(input_path)

    if output_file:
        print(f"\nTranslation successful. Output file: {output_file}", file=sys.stderr)
        # You can add code here to verify the output file content if needed
        return output_file
    else:
        print("\nTranslation failed.", file=sys.stderr)
    return None



def sample():
    """
    Demonstrates how to use the Llm class.
    """
    print("\n--- LLM Sample Call ---")

    llmprovider = os.getenv('LLM_PROVIDER', 'gemini')
    llmtoken = os.getenv('LLM_TOKEN', None)
    llmurl = os.getenv('LLM_URL', None)
    llmmodel = os.getenv('LLM_MODEL', None)
    llmsys = os.getenv('LLM_PROMPT', None)

    # Example 1: Using Gemini (default provider)
    try:
        print(f"\nCalling {llmprovider}...")
        llm = Llm(provider=llmprovider, url=llmurl, token=llmtoken) # Uses GEMINI_API_KEY from environment
        response = llm.run(model=llmmodel, sysprompt=llmsys, userprompt="What is the capital of Italy?")
        print(f"Gemini Response: {response}")
    except Exception as e:
        print(f"Gemini call failed: {e}")


if __name__ == "__main__":
    main()

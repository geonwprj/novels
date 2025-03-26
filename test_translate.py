import pytest
import subprocess
import os

def test_translate_no_runtime_error():
    # Create a dummy input json file for testing with correct filename format
    test_input_file = "test_source-TestBook-0001.json"
    with open(test_input_file, 'w', encoding='utf-8') as f:
        f.write('{"book": "TestBook", "title": "Test Title", "url": "http://test.com", "source": "test_source", "content": "This is a test content."}')

    # Run translate.py with the test input file
    try:
        subprocess.run(["python", "translate.py", test_input_file], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Runtime error during translate.py execution: {e.stderr.decode()}")
    finally:
        # Clean up the test input file
        os.remove(test_input_file)
        # Clean up the output directory if created
        output_dir = "TestBook" # Directory name is based on book title in test_input.json
        if os.path.exists(output_dir) and os.path.isdir(output_dir):
            import shutil
            shutil.rmtree(output_dir)
# src/utils/llm.py
import requests
import json
import os
import base64 # Needed for image encoding
from typing import List, Dict, Any, Optional, Union

# Define default URLs
DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com",
    # Add other providers here if needed
}

# Define default models (can be overridden via kwargs)
DEFAULT_MODELS = {
    "openai": "gpt-4o", # gpt-4o supports vision
    "gemini": "gemini-pro-vision", # Use vision model for image support
}

class Llm:
    """
    A utility class to interact with different LLM providers (OpenAI, Gemini, etc.).
    Handles payload preparation, API calling, and response extraction.
    """
    def __init__(self, provider: str = "gemini", url: Optional[str] = None, token: Optional[str] = None, model: Optional[str] = None):
        """
        Initializes the Llm client.

        Args:
            provider (str): The LLM provider ('openai' or 'gemini'). Defaults to 'gemini'.
            url (Optional[str]): The API endpoint URL. If None, uses the default URL
                                 for the specified provider.
        """
        supported_providers = list(DEFAULT_URLS.keys())
        if provider.lower() not in supported_providers:
            raise ValueError(f"Unsupported provider: {provider}. Supported providers are: {supported_providers}")

        self.provider = provider.lower()
        self.url = url if url is not None else DEFAULT_URLS[self.provider]

        # Note: API keys are typically handled via environment variables
        # or passed securely. For this example, we'll look for env vars.
        self._api_key = token # This is the token for the LLM, not the API key
        if token is None:
            self._api_key = os.environ.get(f"{self.provider.upper()}_API_KEY")
            if not self._api_key and self.provider in ["openai", "gemini"]:
                print(f"Warning: {self.provider.upper()}_API_KEY environment variable not found. API calls may fail.")

        # Store the default model for the provider, can be overridden in run/prepare_payload
        self._default_model = model
        if model is None:
            self._default_model = DEFAULT_MODELS.get(self.provider, "unknown")
        
        if self.provider == 'openai':
            self.url = f"{self.url}/chat/completions" # OpenAI chat completions endpoint
        elif self.provider == 'gemini':
            self.url = f"{self.url}/v1beta/models/{self._default_model}:generateContent?key={token}"

    def prepare_payload(
        self,
        sysprompt: Optional[str] = None,
        userprompt: Optional[str] = None,
        assistprompt: Optional[str] = None,
        image: Optional[Union[str, bytes]] = None, # image can be path (str) or bytes
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Prepares the API request payload based on the provider, using specific prompts and image.

        Args:
            sysprompt (Optional[str]): The system prompt/instructions.
            userprompt (Optional[str]): The main user input prompt.
            assistprompt (Optional[str]): Previous assistant response(s) for context.
            image (Optional[Union[str, bytes]]): Path to an image file (str) or image data (bytes).
                                                 Requires a vision-capable model.
            **kwargs: Additional parameters for the API call (e.g., temperature, model).

        Returns:
            Dict[str, Any]: The prepared payload dictionary.
        """
        payload: Dict[str, Any] = {}
        # Get model from kwargs, default to the instance's default model
        model = kwargs.pop("model", self._default_model)

        # --- Construct messages/contents based on provider ---
        if self.provider == "openai":
            messages: List[Dict[str, Any]] = [] # Use Any because content can be list for vision

            if sysprompt:
                messages.append({"role": "system", "content": sysprompt})

            # OpenAI Vision requires content to be a list of text and image parts
            user_content: List[Dict[str, Any]] = []
            if userprompt:
                user_content.append({"type": "text", "text": userprompt})

            if image:
                try:
                    image_data_base64 = self._encode_image(image)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data_base64}"
                            # Can add 'detail': 'low'/'high'/'auto' here if needed
                        }
                    })
                except Exception as e:
                    print(f"Warning: Could not encode image for OpenAI: {e}")
                    # Decide whether to raise error or proceed without image
                    # For now, we'll print warning and proceed without image part
                    pass # Or raise ValueError(f"Failed to process image: {e}")

            if user_content:
                 messages.append({"role": "user", "content": user_content if len(user_content) > 1 else user_content[0]['text']}) # If only text, keep it simple string

            if assistprompt:
                # OpenAI expects alternating user/assistant roles for conversation history
                # This simple implementation assumes assistprompt is the *last* assistant turn
                # A more complex one would parse assistprompt into multiple turns if needed
                messages.append({"role": "assistant", "content": assistprompt})


            payload = {
                "model": model,
                "messages": messages,
                **kwargs, # Include other kwargs like temperature, max_tokens, etc.
            }

        elif self.provider == "gemini":
            # Gemini expects contents in a different format
            # System instructions are often prepended to the first user message
            # Image handling varies; this example uses base64 which is supported by some Gemini models
            contents: List[Dict[str, Any]] = []

            # Gemini doesn't have a dedicated system role like OpenAI
            # Prepend system prompt to the user prompt
            full_user_prompt = ""
            if sysprompt:
                full_user_prompt += sysprompt + "\n\n"
            if userprompt:
                full_user_prompt += userprompt

            user_parts: List[Dict[str, Any]] = []
            if full_user_prompt:
                 user_parts.append({"text": full_user_prompt})

            if image:
                 try:
                     image_data_base64 = self._encode_image(image)
                     # Gemini expects image data directly in a 'inline_data' part
                     user_parts.append({
                         "inline_data": {
                             "mime_type": "image/jpeg", # Assume JPEG, could add detection
                             "data": image_data_base64
                         }
                     })
                 except Exception as e:
                     print(f"Warning: Could not encode image for Gemini: {e}")
                     pass # Or raise ValueError(f"Failed to process image: {e}")


            if user_parts:
                 contents.append({"role": "user", "parts": user_parts})

            if assistprompt:
                # Gemini uses 'model' role for assistant
                contents.append({"role": "model", "parts": [{"text": assistprompt}]})

            payload = {
                "contents": contents,
                # Gemini parameters are often nested under 'generationConfig' or 'safetySettings'
                # For simplicity, we'll pass top-level kwargs, but a more robust
                # implementation might map common params like temperature.
                # Example: kwargs.get('temperature') could go into generationConfig
                **kwargs
            }
            # Store the requested model for call_api to use in the URL
            self._requested_model = model

        else:
            # This case should ideally not be reached due to the check in __init__
            raise NotImplementedError(f"Payload preparation not implemented for provider: {self.provider}")

        return payload

    def _encode_image(self, image: Union[str, bytes]) -> str:
        """
        Encodes an image (path or bytes) to a base64 string.
        Assumes JPEG format for base64 encoding type.

        Args:
            image (Union[str, bytes]): Path to an image file (str) or image data (bytes).

        Returns:
            str: The base64 encoded image data.

        Raises:
            FileNotFoundError: If the image path does not exist.
            IOError: If there's an error reading the image file.
            TypeError: If the image input is not str or bytes.
        """
        if isinstance(image, str):
            if not os.path.exists(image):
                raise FileNotFoundError(f"Image file not found: {image}")
            try:
                with open(image, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            except IOError as e:
                raise IOError(f"Error reading image file {image}: {e}")
        elif isinstance(image, bytes):
            return base64.b64encode(image).decode('utf-8')
        else:
            raise TypeError("Image must be a file path (str) or bytes.")


    def call_api(self, payload: Dict[str, Any]) -> requests.Response:
        """
        Makes the API call to the configured URL.

        Args:
            payload (Dict[str, Any]): The prepared request payload.

        Returns:
            requests.Response: The response object from the API call.

        Raises:
            requests.exceptions.RequestException: If the API call fails.
            ValueError: If API key is missing for providers requiring it.
        """
        headers = {
            "Content-Type": "application/json",
        }
        request_url = self.url # Start with the base URL from init

        if self.provider == "openai":
            if not self._api_key:
                 raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            headers["Authorization"] = f"Bearer {self._api_key}"
            # OpenAI model is in the payload body

        elif self.provider == "gemini":
            if not self._api_key:
                 raise ValueError("Gemini API key not found. Set GEMINI_API_KEY environment variable.")
            # Gemini API key is typically passed as a query parameter
            # If a specific model was requested via kwargs in prepare_payload, update the URL path
            gemini_model_in_url = self._default_model # Start with default
            if hasattr(self, '_requested_model'):
                gemini_model_in_url = self._requested_model

                # Construct the correct Gemini URL with the model and endpoint
                # Example: https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent
                # base_url_parts = DEFAULT_URLS["gemini"].split('/')
                base_url_parts = self.url.split('/')
                # Find the index of 'models' and replace the part after it
                try:
                    models_index = base_url_parts.index('models')
                    # Reconstruct the URL with the correct model and endpoint (:generateContent)
                    request_url = '/'.join(base_url_parts[:models_index + 1] + [f"{gemini_model_in_url}:generateContent?key={self._api_key}"])
                except ValueError:
                    # Fallback if 'models' isn't in the default URL structure (shouldn't happen with current defaults)
                    print(f"Warning: 'models' not found in default Gemini URL structure. Using base URL: {self.url}")
                    request_url = self.url # Use the URL from init as fallback

                # request_url = f"{request_url}?key={self._api_key}"
                request_url = request_url
            else:
                request_url = self.url


        else:
             raise NotImplementedError(f"API call not implemented for provider: {self.provider}")


        try:
            response = requests.post(request_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.RequestException as e:
            print(f"API call failed for {self.provider} at {request_url}: {e}")
            # Attempt to print response body if available for debugging
            if hasattr(e, 'response') and e.response is not None:
                 try:
                     print(f"Response body: {e.response.text}")
                 except Exception:
                     pass # Ignore if response body can't be printed
            raise # Re-raise the exception after printing info


    def extract_response(self, api_response: requests.Response) -> str:
        """
        Extracts the text content from the API response.

        Args:
            api_response (requests.Response): The response object from call_api.

        Returns:
            str: The extracted text content.

        Raises:
            ValueError: If the response format is unexpected or content is missing.
        """

        if not api_response.ok:
            print(ValueError(f"API response not OK: {api_response.status_code} - {api_response.text}"))
            return api_response.status_code, None # Return the raw response text if not OK

        try:
            response_data = api_response.json()
        except json.JSONDecodeError:
            raise ValueError(f"Failed to decode JSON response from {self.provider}: {api_response.text}")

        if self.provider == "openai":
            # OpenAI format: response_data['choices'][0]['message']['content']
            if 'choices' in response_data and len(response_data['choices']) > 0:
                choice = response_data['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    # Content can be a string or a list of parts (for vision)
                    content = choice['message']['content']
                    if isinstance(content, list):
                        # If it's a list (e.g., vision response), concatenate text parts
                        return None, "".join(part.get('text', '') for part in content if part.get('type') == 'text')
                    elif isinstance(content, str):
                        return None, content
                    else:
                         raise ValueError(f"Unexpected content type in OpenAI response: {type(content)}")
                elif 'text' in choice: # Handle older completions API format if necessary
                     return None, choice['text']

        elif self.provider == "gemini":
            if 'promptFeedback' in response_data:
                try:
                    block_reason = response_data['promptFeedback']['blockReason']
                    return 'TOKEN_EXCEEDED', None
                except Exception as e:
                    raise ValueError(f"Failed to extract block reasons from Gemini response: {e}")

            # Gemini format: response_data['candidates'][0]['content']['parts'][0]['text']
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                    # Concatenate text from all parts if multiple exist
                    # Note: Gemini can return image parts, but we only extract text here
                    return None, "".join(part.get('text', '') for part in candidate['content']['parts'] if 'text' in part)
                # Handle potential 'finishReason' or 'safetyRatings' indicating no text response
                if 'finishReason' in candidate:
                     # Check if finishReason indicates a block
                     block_reasons = ["SAFETY", "OTHER"] # Add other block reasons if known
                     if candidate['finishReason'] in block_reasons:
                          safety_ratings = candidate.get('safetyRatings', 'N/A')
                          raise ValueError(f"Gemini response blocked by finish reason: {candidate['finishReason']}. Safety ratings: {safety_ratings}")
                     # Otherwise, it might be 'STOP' or 'MAX_TOKENS', which are not errors
                     # If there's no text content despite a non-error finish reason, it's still unexpected
                     if not candidate['content']['parts']:
                          raise ValueError(f"Gemini response finished with reason: {candidate['finishReason']}, but no content parts found.")
                     # If there are parts but no text, the loop above handles it by returning ""

                if 'safetyRatings' in candidate:
                     # Optionally log safety issues even if not fully blocked
                     print(f"Gemini response has safety ratings: {candidate['safetyRatings']}")
                     # If no text was extracted, and safety ratings are present, it might be the cause
                     if not candidate['content']['parts'] or not any('text' in part for part in candidate['content']['parts']):
                          raise ValueError("Gemini response likely blocked due to safety concerns (no text extracted).")


        # If we reach here, the expected structure was not found or no text was extractable
        raise ValueError(f"Could not extract text from {self.provider} response. Unexpected format or missing text content: {response_data}")

    def run(
        self,
        userprompt: Optional[str] = None,
        sysprompt: Optional[str] = None,
        assistprompt: Optional[str] = None,
        image: Optional[Union[str, bytes]] = None,
        **kwargs: Any
    ) -> str:
        """
        Runs the full LLM interaction process: prepare payload, call API, extract response.

        Args:
            userprompt (Optional[str]): The main user input prompt.
            sysprompt (Optional[str]): The system prompt/instructions.
            assistprompt (Optional[str]): Previous assistant response(s) for context.
            image (Optional[Union[str, bytes]]): Path to an image file (str) or image data (bytes).
                                                 Requires a vision-capable model.
            **kwargs: Additional parameters for the API call.

        Returns:
            str: The extracted text response from the LLM.

        Raises:
            Exception: Propagates exceptions from prepare_payload, call_api, or extract_response.
        """
        
        from .common import format_dict_for_debug

        try:
            # Pass all relevant arguments to prepare_payload
            payload = self.prepare_payload(
                sysprompt=sysprompt,
                userprompt=userprompt,
                assistprompt=assistprompt,
                image=image,
                **kwargs # Pass through any extra kwargs like temperature, model etc.
            )
            # print(f"payload: {format_dict_for_debug(payload, 200, 100, 100)}")
            # print(f"payload: {payload}")
            api_response = self.call_api(payload)
            error, extracted_text = self.extract_response(api_response)
            return error, extracted_text
        except Exception as e:
            print(f"An error occurred during the LLM run: {e}")
            raise # Re-raise the exception

    # Note on Image Output:
    # Standard text generation APIs like the ones used here (OpenAI Chat, Gemini Pro/Vision)
    # return text responses. If the LLM generates a description of an image,
    # a URL to an image, or other image-related text, this will be captured
    # by the `extract_response` method as part of the text output.
    # The API does not return image files or binary image data directly in this format.


# llm_model.py

import tiktoken
import os
import time
from vertexai.preview import tokenization # Keep for token counting if preferred
# Or use the direct model's count_tokens if switching fully away from vertexai preview
# from google.generativeai import GenerativeModel # Needed if using direct API's count_tokens

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
# Remove LlamaCpp/Ollama specific imports if not needed in this file
# from langchain_community.llms import LlamaCpp
# from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
# from langchain_ollama import OllamaEmbeddings
# from llama_cpp import Llama
# from contextlib import redirect_stdout, redirect_stderr
# from langchain_ollama.llms import OllamaLLM

from .logger import Logger
from ..config import config as cfg # Assuming config has GEMINI_LLM_MODEL
from pydantic import BaseModel # Needed for type hinting schema
from typing import Type, Optional

# Mapping from known model names to their RPM limits (based on your image)
# Add other models as needed
MODEL_RPM_LIMITS = {
    "gemini-2.5-pro-experimental": 5,
    "gemini-2.0-flash": 15,
    "gemini-2.0-flash-experimental": 10, # Assuming same as non-experimental if not specified
    "gemini-2.0-flash-lite": 30,
    "gemini-2.0-flash-thinking-experimental-01-21": 10,
    "gemini-1.5-flash": 15,
    "gemini-1.5-flash-8b": 15,
    "gemini-1.5-pro": 2,
    "gemma-3": 30, # Assuming this is gemma 3 based on image
    # Add default or handle missing models
    "default": 15 # A reasonable default if model not found
}


class LLMModel:
    """
    Provide common interface for different LLM models.
    """
    def __init__(self):
        self._logger = Logger()
        self.model = None
        self.embedding = None
        self.context_size = 0
        self._last_api_call_time: Optional[float] = None
        self.rpm_limit: int = 15 # Default RPM
        self.min_request_interval: float = 60.0 / self.rpm_limit

    def _wait_for_rate_limit(self):
        """Checks and waits if the time since the last call is less than the required interval."""
        if self._last_api_call_time is None:
            return # No need to wait for the first call

        now = time.monotonic()
        time_since_last = now - self._last_api_call_time
        wait_needed = self.min_request_interval - time_since_last

        if wait_needed > 0:
            self._logger.debug(f"Rate limit check: Waiting for {wait_needed:.2f} seconds.")
            time.sleep(wait_needed)
        # No logging if no wait needed to avoid clutter

    def _update_last_call_time(self):
        """Updates the timestamp of the last API call."""
        self._last_api_call_time = time.monotonic()

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        raise NotImplementedError

    def token_count(self, prompt: str | None) -> int:
        raise NotImplementedError


class GeminiModel(LLMModel):
    """
    Gemini model implementation using LangChain, with improved rate limiting.
    """
    def __init__(self):
        super().__init__()

        # --- Model Setup ---
        self.context_size = 1000000 # Example, adjust based on actual model limits if needed
        self.model_name = cfg.GEMINI_LLM_MODEL # e.g., "gemini-2.0-flash-lite"

        # --- Rate Limiting Setup ---
        self.rpm_limit = MODEL_RPM_LIMITS.get(self.model_name, MODEL_RPM_LIMITS["default"])
        if self.rpm_limit <= 0:
             self._logger.warning(f"RPM limit for {self.model_name} is zero or invalid. Disabling rate limiting wait.")
             self.min_request_interval = 0
        else:
            self.min_request_interval = 60.0 / self.rpm_limit
        self._logger.info(f"Initialized GeminiModel: {self.model_name}. Rate limit: {self.rpm_limit} RPM (Min interval: {self.min_request_interval:.2f}s)")


        # --- API Key and LangChain Initialization ---
        api_key = os.environ.get('GENAI_API_KEY')
        if api_key is None:
            self._logger.error("GENAI_API_KEY environment variable not set.")
            raise ValueError("GENAI_API_KEY environment variable not set.")
        # Langchain uses GOOGLE_API_KEY, so set it.
        os.environ["GOOGLE_API_KEY"] = api_key

        try:
            self.model = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=0,
                verbose=False,
                # convert_system_message_to_human=True # Might be needed depending on LangChain/model version
            )
            # Set the embedding model
            self.embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", task_type="retrieval_document") # Specify task_type

            self._logger.info(f"Gemini model {self.model_name} initialized successfully via LangChain.")
        except Exception as e:
            self._logger.error(f"Error initializing LangChain Gemini model: {e}")
            raise # Re-raise the exception

    def token_count(self, prompt: str | None) -> int:
        if prompt is None:
            return 0
        # Using vertexai preview tokenizer as in original code
        # Ensure 'google-cloud-aiplatform' is installed and authenticated if using this
        try:
            # Make sure the model name passed here is compatible with the tokenizer
            # Using a known compatible model like 'gemini-1.5-flash' might be safer
            # if the specific one like 'gemini-2.0-flash-lite' isn't directly supported by the preview tokenizer.
            tokenizer_model_name = "gemini-1.5-flash" # Or try self.model_name
            tokenizer = tokenization.get_tokenizer_for_model(tokenizer_model_name)
            result = tokenizer.count_tokens(prompt)
            return result.total_tokens
        except Exception as e:
            self._logger.warning(f"Could not count tokens using vertexai tokenizer for model {self.model_name} (tried with {tokenizer_model_name}): {e}. Falling back to basic estimate.")
            # Fallback: very rough estimate (split by spaces)
            return len(prompt.split())

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        """Generates content using the Gemini model, optionally with structured output."""
        self._wait_for_rate_limit() # Wait before making the call

        try:
            if schema:
                self._logger.debug(f"Attempting structured output with schema: {schema.__name__}")
                structured_model = self.model.with_structured_output(schema, include_raw=False)
                # It seems the .invoke call itself was printing the schema info in your test.
                # Let's see if it still does and if it returns data now.
                response = structured_model.invoke(prompt)
                self._logger.debug(f"Structured output response type: {type(response)}")
                if response is None:
                     self._logger.warning(f"Structured output for schema {schema.__name__} returned None.")
                # If response is not None, it should be an instance of the schema class
                output = response
            else:
                self._logger.debug("Generating standard text output.")
                response = self.model.invoke(prompt)
                output = response.content # Extract text content

            self._update_last_call_time() # Update time only after successful call
            return output

        except Exception as e:
            self._logger.error(f"Error during Gemini API call: {e}")
            # Don't update last call time if it failed
            # Depending on the error, you might want to implement retries
            raise # Re-raise the exception to signal failure

# Example Usage (similar to llm.py, adjust imports)
if __name__ == '__main__':
    from pydantic import Field # Add this import
    from typing import List # Add this import

    # Configure logger (replace with your actual logger setup)
    cfg.LOGGER_NAME = "test_llm"
    cfg.LOG_FILE = "test_llm.log"
    cfg.GEMINI_LLM_MODEL = "gemini-2.0-flash-lite" # Set the model to test

    # Ensure GENAI_API_KEY is set in your environment
    if 'GENAI_API_KEY' not in os.environ:
        print("Error: GENAI_API_KEY environment variable not set.")
        exit()

    # Define a Pydantic schema FOR TESTING
    # NOTE: Use List[int] for a list of integers!
    class TestSchema(BaseModel):
        list_of_int: List[int] = Field(description="list of 10 integers generated")

    test_prompt = "Generate a list containing exactly 10 different integer numbers."

    try:
        print("Initializing GeminiModel...")
        gemini_model = GeminiModel()

        print("\nTesting standard generation:")
        standard_response = gemini_model.generate(test_prompt)
        print("Standard Response:")
        print(standard_response)

        print("\nTesting structured generation:")
        # Use the corrected schema type
        structured_response = gemini_model.generate(test_prompt, schema=TestSchema)
        print("Structured Response:")
        print(structured_response)
        print(f"Type of structured response: {type(structured_response)}")

        if isinstance(structured_response, TestSchema):
             print("Successfully parsed into TestSchema object.")
             print(f"Generated list: {structured_response.list_of_int}")
        elif structured_response is None:
             print("Structured response was None.")
        else:
             print("Structured response was not None, but not the expected Pydantic object.")


        print("\nTesting token count:")
        count = gemini_model.token_count(test_prompt)
        print(f"Token count for prompt: {count}")


    except Exception as e:
        print(f"\nAn error occurred: {e}")

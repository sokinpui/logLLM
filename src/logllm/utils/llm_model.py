# llm_model_direct_api.py

import os
import time
import json
from typing import Type, Optional, Dict, Any, List

# Pydantic related imports
from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined

# Google Generative AI API
import google.generativeai as genai
from google.ai.generativelanguage import Tool, FunctionDeclaration, Schema, Type as GoogleApiType

# Langchain components for embedding (can keep using this)
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Your project's logger and config
from .logger import Logger
from ..config import config as cfg # Assuming config has GEMINI_LLM_MODEL


# --- Pydantic to Google API Tool Converter (Updated) ---
# (Keep the previously fixed pydantic_to_google_tool function here)
# Mapping from Pydantic/JSON Schema types to Google API types
TYPE_MAP = {
    "string": GoogleApiType.STRING,
    "integer": GoogleApiType.INTEGER,
    "number": GoogleApiType.NUMBER,
    "boolean": GoogleApiType.BOOLEAN,
    "array": GoogleApiType.ARRAY,
    "object": GoogleApiType.OBJECT,
}

def pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool:
    """
    Converts a Pydantic model into a Google Generative AI Tool,
    handling Optional types correctly.
    """
    schema_dict = pydantic_model.model_json_schema()

    properties = schema_dict.get("properties", {})
    required_fields = schema_dict.get("required", [])
    model_description = schema_dict.get("description", pydantic_model.__doc__ or f"Schema for {pydantic_model.__name__}")

    google_properties = {}
    for name, prop_schema in properties.items():
        google_type = GoogleApiType.TYPE_UNSPECIFIED
        prop_description = prop_schema.get("description", "")
        items_schema = None
        prop_type_str = None

        if "anyOf" in prop_schema:
            for type_option in prop_schema["anyOf"]:
                if type_option.get("type") != "null":
                    prop_type_str = type_option.get("type")
                    prop_description = type_option.get("description", prop_description)
                    break
        else:
            prop_type_str = prop_schema.get("type")

        if prop_type_str:
            google_type = TYPE_MAP.get(prop_type_str, GoogleApiType.TYPE_UNSPECIFIED)

        if google_type == GoogleApiType.ARRAY and "items" in prop_schema:
             items_prop_schema = prop_schema["items"]
             items_type_str = items_prop_schema.get("type")
             items_google_type = TYPE_MAP.get(items_type_str, GoogleApiType.TYPE_UNSPECIFIED)
             if items_google_type != GoogleApiType.TYPE_UNSPECIFIED:
                 items_schema = Schema(type=items_google_type, description=items_prop_schema.get("description",""))
             else:
                 pass

        if google_type != GoogleApiType.TYPE_UNSPECIFIED:
            google_properties[name] = Schema(
                type=google_type,
                description=prop_description,
                items=items_schema
            )
        else:
            print(f"Warning: Could not map Pydantic type for property '{name}'. Schema details: {prop_schema}")

    function_declaration = FunctionDeclaration(
        name=pydantic_model.__name__,
        description=model_description,
        parameters=Schema(
            type=GoogleApiType.OBJECT,
            properties=google_properties,
            required=required_fields,
        ),
    )
    return Tool(function_declarations=[function_declaration])


# --- Rate Limiting Configuration ---
MODEL_RPM_LIMITS = {
    "gemini-2.5-pro-experimental": 5,
    "gemini-2.0-flash": 15,
    "gemini-2.0-flash-experimental": 10,
    "gemini-2.0-flash-lite": 30,
    "gemini-2.0-flash-thinking-experimental-01-21": 10,
    "gemini-1.5-flash": 15, # Keep updated based on actual limits
    "gemini-1.5-flash-latest": 15, # Assuming same as 1.5 flash
    "gemini-1.5-flash-8b": 15,
    "gemini-1.5-pro": 2,
    "gemma-3": 30,
    "default": 15
}

# --- Base LLM Model Class ---
class LLMModel:
    """Provide common interface for different LLM models."""
    def __init__(self):
        # Ensure Logger() gets initialized correctly based on your project structure
        self._logger = Logger()
        self.model = None
        self.embedding = None
        self.context_size = 0
        self._last_api_call_time: Optional[float] = None
        self.rpm_limit: int = 15 # Default RPM
        self.min_request_interval: float = 60.0 / self.rpm_limit

    def _wait_for_rate_limit(self):
        if self._last_api_call_time is None: return
        now = time.monotonic()
        time_since_last = now - self._last_api_call_time
        wait_needed = self.min_request_interval - time_since_last
        if wait_needed > 0:
            self._logger.debug(f"Rate limit check: Waiting for {wait_needed:.2f} seconds.")
            time.sleep(wait_needed)

    def _update_last_call_time(self):
        self._last_api_call_time = time.monotonic()

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        raise NotImplementedError

    def token_count(self, prompt: str | None) -> int:
        raise NotImplementedError

# --- Direct API Gemini Model (with fix) ---
class GeminiModel(LLMModel):
    """
    Gemini model implementation using the direct google-generativeai API,
    with Pydantic schema support and improved rate limiting.
    """
    def __init__(self):
        super().__init__()
        self.context_size = 1000000 # Example context size
        self.model_name = cfg.GEMINI_LLM_MODEL

        api_model_name_key = self.model_name.split('/')[-1]
        self.rpm_limit = MODEL_RPM_LIMITS.get(api_model_name_key, MODEL_RPM_LIMITS["default"])

        if self.rpm_limit <= 0:
             self._logger.warning(f"RPM limit for {self.model_name} is zero or invalid. Disabling rate limiting wait.")
             self.min_request_interval = 0
        else:
            self.min_request_interval = 60.0 / self.rpm_limit
        self._logger.info(f"Initialized Direct API GeminiModel: {self.model_name}. Rate limit: {self.rpm_limit} RPM (Min interval: {self.min_request_interval:.2f}s)")

        api_key = os.environ.get('GENAI_API_KEY')
        if api_key is None:
            self._logger.error("GENAI_API_KEY environment variable not set.")
            raise ValueError("GENAI_API_KEY environment variable not set.")

        try:
            genai.configure(api_key=api_key)
            self.generation_config = genai.GenerationConfig(temperature=0.0)
            self.safety_settings = {} # Configure as needed

            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            os.environ["GOOGLE_API_KEY"] = api_key # For Langchain Embeddings if it checks
            self.embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", task_type="retrieval_document")
            self._logger.info(f"Gemini model {self.model_name} initialized successfully via google-generativeai.")
        except Exception as e:
            self._logger.error(f"Error initializing google-generativeai model: {e}")
            raise

    def token_count(self, prompt: str | None) -> int:
        # (token_count method remains the same)
        if prompt is None:
            return 0
        try:
            return self.model.count_tokens(prompt).total_tokens
        except Exception as e:
            self._logger.warning(f"Could not count tokens using google-generativeai for model {self.model_name}: {e}. Falling back to basic estimate.")
            return len(prompt.split())

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        """Generates content using the Gemini model, optionally with structured output via tools."""
        self._wait_for_rate_limit()

        tools = None
        tool_config = None
        if schema:
            try:
                tools = [pydantic_to_google_tool(schema)]
                tool_config = {'function_calling_config': {'mode': 'ANY'}} # Use the nested structure for mode
                self._logger.debug(f"Attempting structured output with schema tool: {schema.__name__}")
            except Exception as e:
                self._logger.error(f"Failed to convert Pydantic schema {schema.__name__} to Google Tool: {e}", exc_info=True) # Log traceback
                tools = None
                tool_config = None
                self._logger.warning("Proceeding with standard text generation due to schema conversion error.")

        try:
            response = self.model.generate_content(
                prompt,
                tools=tools,
                tool_config=tool_config
            )
            self._update_last_call_time()

            # --- Process the response ---
            if schema and response.candidates and response.candidates[0].content.parts:
                function_call_part = None
                for part in response.candidates[0].content.parts:
                     if hasattr(part, 'function_call') and part.function_call:
                         function_call_part = part
                         break

                if function_call_part:
                    fc = function_call_part.function_call
                    self._logger.debug(f"Model returned function call: {fc.name}")

                    if fc.name != schema.__name__:
                         self._logger.warning(f"Model called function '{fc.name}' but expected '{schema.__name__}'. Attempting to parse anyway.")

                    # --- THE FIX IS HERE ---
                    try:
                        # Convert the MapComposite object (fc.args) to a standard dict
                        args_dict = dict(fc.args)
                        self._logger.debug(f"Extracted args from function call: {args_dict}")
                    except Exception as dict_conv_error:
                        self._logger.error(f"Failed to convert function call args to dict: {dict_conv_error}", exc_info=True)
                        self._logger.error(f"Raw args object type: {type(fc.args)}, content: {fc.args}")
                        return None # Cannot proceed if args conversion fails

                    # --- End of Fix ---

                    try:
                        parsed_schema_obj = schema.model_validate(args_dict)
                        self._logger.debug(f"Successfully parsed response into schema: {schema.__name__}")
                        return parsed_schema_obj
                    except Exception as pydantic_error:
                        self._logger.error(f"Pydantic validation failed for schema {schema.__name__}: {pydantic_error}", exc_info=True)
                        self._logger.error(f"Dict args that failed validation: {args_dict}")
                        return None
                else:
                     self._logger.warning(f"Schema {schema.__name__} provided, but model did not return a function call. Checking for text fallback.")
                     # Fall through to check for text content even if function call wasn't made

            # --- Handle regular text response (or fallback) ---
            try:
                text_content = response.text
                # Check if text is empty even if no error occurred (e.g., safety blocking with no text)
                if not text_content and (not schema or not function_call_part): # Avoid false positive if struct output failed validation but text is empty
                     self._logger.warning("Response contained no text content (potentially blocked or empty generation).")
                     try:
                         self._logger.debug(f"Prompt feedback: {response.prompt_feedback}")
                         self._logger.debug(f"Finish reason: {response.candidates[0].finish_reason}")
                     except Exception: pass
                     return None
                return text_content
            except ValueError: # This specific error is raised by .text if blocked
                 self._logger.warning("Response blocked due to safety settings or other reasons (ValueError accessing .text).")
                 try:
                     self._logger.debug(f"Prompt feedback: {response.prompt_feedback}")
                     self._logger.debug(f"Finish reason: {response.candidates[0].finish_reason}") # Add finish reason
                     self._logger.debug(f"Safety Ratings: {response.candidates[0].safety_ratings}") # Add safety ratings
                 except Exception: pass
                 return None
            except AttributeError: # If response structure is unexpected
                 self._logger.error("Unexpected response structure, cannot access .text", exc_info=True)
                 return None
            except Exception as text_extract_err:
                 self._logger.error(f"Unexpected error extracting text from response: {text_extract_err}", exc_info=True)
                 return None

        except Exception as e:
            self._logger.error(f"Error during Gemini API call (google-generativeai): {e}", exc_info=True) # Add traceback to log
            # Don't update last call time if it failed
            raise # Re-raise the exception


# --- Example Usage (main function remains the same) ---
def main():
    cfg.LOGGER_NAME = "test_llm_direct"
    cfg.LOG_FILE = "test_llm_direct.log"
    # Ensure model name in config is valid for the API, e.g., "gemini-1.5-flash-latest"
    cfg.GEMINI_LLM_MODEL = "gemini-1.5-flash-latest"

    if 'GENAI_API_KEY' not in os.environ:
        print("Error: GENAI_API_KEY environment variable not set.")
        exit()

    class TestSchemaDirect(BaseModel):
        """Schema to hold a list of generated integers."""
        numbers_list: List[int] = Field(..., description="A list containing exactly 5 different integer numbers.")
        comment: Optional[str] = Field(None, description="An optional comment about the list.")

    test_prompt = "Generate a list of 5 distinct integers. Add a short comment."

    try:
        print("Initializing Direct API GeminiModel...")
        logger = Logger() # Ensure logger is initialized if needed globally
        gemini_model = GeminiModel()

        print("\nTesting standard generation (Direct API):")
        standard_response = gemini_model.generate(test_prompt)
        print("Standard Response:")
        print(standard_response)

        print("\nTesting structured generation (Direct API):")
        structured_response = gemini_model.generate(test_prompt, schema=TestSchemaDirect)
        print("Structured Response:")
        print(structured_response)
        print(f"Type of structured response: {type(structured_response)}")

        if isinstance(structured_response, TestSchemaDirect):
             print("Successfully parsed into TestSchemaDirect object.")
             print(f"Generated list: {structured_response.numbers_list}")
             print(f"Comment: {structured_response.comment}")
        elif structured_response is None:
             print("Structured response was None. Check logs for errors (API, validation, or blocking).")
        else:
             print(f"Structured response was not the expected Pydantic object, it was text: {structured_response}")


        print("\nTesting token count (Direct API):")
        count = gemini_model.token_count(test_prompt)
        print(f"Token count for prompt: {count}")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

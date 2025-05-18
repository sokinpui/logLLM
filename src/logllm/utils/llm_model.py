# llm_model_direct_api.py

import json
import os
import time
from typing import Any, Dict, List, Optional, Type, Union  # Added Union

# Google Generative AI API
import google.generativeai as genai
from google.ai.generativelanguage import (
    FunctionDeclaration,
    Schema,
    Tool,
)
from google.ai.generativelanguage import Type as GoogleApiType
from google.generativeai import types as genai_types  # For EmbedContentResponse hint

# Pydantic related imports
from pydantic import BaseModel, Field

# Assuming config has GEMINI_LLM_MODEL and potentially GEMINI_EMBEDDING_MODEL
from ..config import config as cfg

# Your project's logger and config
from .logger import Logger

# from pydantic_core import PydanticUndefined # Not used in the provided snippet


# Attempt to import Vertex AI tokenizer
try:
    from vertexai.preview import tokenization

    VERTEX_TOKENIZER_AVAILABLE = True
except ImportError:
    VERTEX_TOKENIZER_AVAILABLE = False
    print(
        "Warning: vertexai.preview.tokenization not found. Local token counting will be disabled. "
        "Consider installing google-cloud-aiplatform for this feature."
    )


# --- Pydantic to Google API Tool Converter ---
TYPE_MAP = {
    "string": GoogleApiType.STRING,
    "integer": GoogleApiType.INTEGER,
    "number": GoogleApiType.NUMBER,
    "boolean": GoogleApiType.BOOLEAN,
    "array": GoogleApiType.ARRAY,
    "object": GoogleApiType.OBJECT,
}


def pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool:
    schema_dict = pydantic_model.model_json_schema()
    properties = schema_dict.get("properties", {})
    required_fields = schema_dict.get("required", [])
    model_description = schema_dict.get(
        "description", pydantic_model.__doc__ or f"Schema for {pydantic_model.__name__}"
    )
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
            items_google_type = TYPE_MAP.get(
                items_type_str, GoogleApiType.TYPE_UNSPECIFIED
            )
            if items_google_type != GoogleApiType.TYPE_UNSPECIFIED:
                items_schema = Schema(
                    type=items_google_type,
                    description=items_prop_schema.get("description", ""),
                )
        if google_type != GoogleApiType.TYPE_UNSPECIFIED:
            google_properties[name] = Schema(
                type=google_type, description=prop_description, items=items_schema
            )
        else:
            # This print might be too noisy, consider using logger if available
            # print(f"Warning: Could not map Pydantic type for property '{name}'. Schema: {prop_schema}")
            pass  # Warning already logged by calling function or handled by TYPE_UNSPECIFIED
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
    "gemini-2.5-flash-preview-04-17": 10,
    "gemini-2.5-pro-preview-05-06": 5,
    "gemini-2.0-flash": 15,
    "gemini-2.0-flash-preview-image-generation": 10,
    "gemini-2.0-flash-experimental": 10,
    "gemini-2.0-flash-lite": 30,
    "gemini-1.5-flash": 15,
    "gemini-1.5-flash-latest": 15,
    "gemini-1.5-flash-001": 15,
    "gemini-1.5-flash-8b": 15,
    "gemini-1.5-pro": 2,
    "gemini-1.5-pro-latest": 2,
    # Embedding models (RPMs can vary, add them if known and if rate limiting is applied to them)
    "models/embedding-001": 1500,  # General RPM for embedding-001
    "embedding-001": 1500,  # Alias
    "models/gemini-embedding-exp-03-07": 5,  # From user image
    "gemini-embedding-exp-03-07": 5,  # Alias
    "default": 15,
}


# --- Base LLM Model Class ---
class LLMModel:
    def __init__(self):
        self._logger = Logger()
        self.model = None
        # self.embedding = None # Removed, embedding handled by specific methods now
        self.context_size = 0
        self._last_api_call_time: Optional[float] = None
        self.rpm_limit: int = 15
        self.min_request_interval: float = 60.0 / self.rpm_limit

    def _wait_for_rate_limit(self, model_rpm: Optional[int] = None):
        current_rpm_limit = model_rpm or self.rpm_limit
        if current_rpm_limit <= 0:  # No limit or invalid
            return

        min_interval = 60.0 / current_rpm_limit

        if self._last_api_call_time is None:
            return  # No previous call, no need to wait

        now = time.monotonic()
        time_since_last = now - self._last_api_call_time
        wait_needed = min_interval - time_since_last
        if wait_needed > 0:
            self._logger.debug(
                f"Rate limit check (target RPM: {current_rpm_limit}): Waiting for {wait_needed:.2f} seconds."
            )
            time.sleep(wait_needed)

    def _update_last_call_time(self):
        self._last_api_call_time = time.monotonic()

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        raise NotImplementedError

    def token_count(self, prompt: str | None) -> int:
        raise NotImplementedError

    def generate_embeddings(
        self,
        contents: Union[str, List[str]],
        embedding_model_name: Optional[str] = None,
        task_type: Optional[str] = None,
        title: Optional[str] = None,
        output_dimensionality: Optional[int] = None,
    ) -> List[List[float]]:
        raise NotImplementedError


# --- Direct API Gemini Model ---
class GeminiModel(LLMModel):
    def __init__(self, model_name: str | None = None):
        super().__init__()
        if model_name:
            self.model_name = (
                model_name  # Full model path e.g. "models/gemini-1.5-pro-latest"
            )
        else:
            self.model_name = cfg.GEMINI_LLM_MODEL

        self.api_model_name_key = self.model_name.split("/")[-1]  # For RPM dict lookup
        self.rpm_limit = MODEL_RPM_LIMITS.get(
            self.api_model_name_key, MODEL_RPM_LIMITS["default"]
        )

        if self.rpm_limit <= 0:
            self._logger.warning(
                f"RPM limit for generation model {self.model_name} is zero or invalid. Rate limiting wait may be affected."
            )
            self.min_request_interval = 0  # Effectively disables waiting for generation
        else:
            self.min_request_interval = 60.0 / self.rpm_limit

        # Default embedding model
        self.default_embedding_model: str = getattr(
            cfg, "GEMINI_EMBEDDING_MODEL", "models/embedding-001"
        )
        self._logger.info(
            f"Initialized Direct API GeminiModel: {self.model_name} (RPM: {self.rpm_limit}). "
            f"Default embedding model: {self.default_embedding_model}."
        )

        api_key = os.environ.get("GENAI_API_KEY")
        if api_key is None:
            self._logger.error("GENAI_API_KEY environment variable not set.")
            raise ValueError("GENAI_API_KEY environment variable not set.")

        try:
            genai.configure(api_key=api_key)
            # For Langchain components that might still look for it
            os.environ["GOOGLE_API_KEY"] = api_key

            self.generation_config = genai.GenerationConfig(temperature=1.0)
            self.safety_settings = {}  # Configure as needed

            self.model = genai.GenerativeModel(  # For text generation
                model_name=self.model_name,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings,
            )
            self._logger.info(
                f"Generative model {self.model_name} initialized successfully."
            )
            if not VERTEX_TOKENIZER_AVAILABLE:
                self._logger.warning(
                    "vertexai.preview.tokenization not available. Local token counting will be skipped."
                )

        except Exception as e:
            self._logger.error(
                f"Error initializing google-generativeai: {e}", exc_info=True
            )
            raise

    def token_count(self, prompt: str | None) -> int:
        if prompt is None:
            self._logger.debug("Token count requested for None prompt, returning 0.")
            return 0
        if VERTEX_TOKENIZER_AVAILABLE:
            try:
                tokenizer_model_key = "gemini-1.5-flash-001"
                self._logger.debug(
                    f"Attempting local token count with vertexai for model key: {tokenizer_model_key}"
                )
                tokenizer = tokenization.get_tokenizer_for_model(tokenizer_model_key)
                count_response = tokenizer.count_tokens(prompt)
                self._logger.info(
                    f"VertexAI token count for '{tokenizer_model_key}': {count_response.total_tokens} tokens."
                )
                return count_response.total_tokens
            except Exception as e_vertex:
                self._logger.warning(
                    f"Local token count with vertexai for '{tokenizer_model_key}' failed: {e_vertex}. Falling back."
                )
        try:
            self._logger.debug(
                f"Attempting API token count with genai for model {self.model_name}"
            )
            # self.model is genai.GenerativeModel
            count = self.model.count_tokens(prompt).total_tokens
            self._logger.info(
                f"GenAI API token count for '{self.model_name}': {count} tokens."
            )
            return count
        except Exception as e_genai:
            self._logger.warning(
                f"API token count with genai failed for {self.model_name}: {e_genai}. Falling back to basic estimate."
            )
            estimated_tokens = len(prompt.split())
            self._logger.info(f"Basic estimate token count: {estimated_tokens} tokens.")
            return estimated_tokens

    def generate_embeddings(
        self,
        contents: Union[str, List[str]],
        embedding_model_name: Optional[str] = None,
        task_type: Optional[str] = None,
        title: Optional[str] = None,
        output_dimensionality: Optional[int] = None,
    ) -> List[List[float]]:
        model_to_use = embedding_model_name or self.default_embedding_model
        embedding_model_key = model_to_use.split("/")[-1]
        embedding_rpm = MODEL_RPM_LIMITS.get(
            embedding_model_key, MODEL_RPM_LIMITS["default"]
        )

        # Apply rate limiting for the embedding model
        # Note: This uses the same _last_api_call_time as generate().
        # If generate and embed are called in rapid succession from different threads,
        # this shared timestamp could lead to contention or slightly off timing.
        # For highly concurrent scenarios, separate rate limiters might be better.
        self._wait_for_rate_limit(model_rpm=embedding_rpm)

        num_items = len(contents) if isinstance(contents, list) else 1
        self._logger.info(
            f"Generating embeddings with model: {model_to_use} (RPM: {embedding_rpm}) for {num_items} item(s). "
            f"Task: {task_type}, Title: {'Yes' if title else 'No'}, Dim: {output_dimensionality}."
        )

        is_single_string_input = isinstance(contents, str)
        api_input_content: Union[str, List[str]]

        if is_single_string_input:
            if not contents:  # type: ignore
                self._logger.warning(
                    "Received empty string for embedding. Returning empty list."
                )
                return []
            api_input_content = contents  # type: ignore
        else:  # List input
            if not contents:  # Empty list
                self._logger.debug(
                    "Received empty list for embedding. Returning empty list."
                )
                return []
            # Filter out empty strings as API requires content with at least 1 character
            api_input_content = [text for text in contents if text]  # type: ignore
            if not api_input_content:
                self._logger.warning(
                    "All texts in input list were empty after filtering. Returning empty list."
                )
                return []
            if len(api_input_content) < len(contents):  # type: ignore
                self._logger.info(f"Filtered out {len(contents) - len(api_input_content)} empty strings from batch embedding.")  # type: ignore

        try:
            response: genai_types.EmbedContentResponse = genai.embed_content(
                model=model_to_use,
                content=api_input_content,
                task_type=task_type,  # type: ignore [arg-type] # SDK handles str for TaskType
                title=title,
                output_dimensionality=output_dimensionality,
            )
            self._update_last_call_time()  # Update after successful API call

            # response['embedding'] is List[float] if api_input_content was str
            # response['embedding'] is List[List[float]] if api_input_content was List[str]
            raw_embeddings = response["embedding"]

            if is_single_string_input:
                if isinstance(raw_embeddings, list) and (
                    not raw_embeddings or isinstance(raw_embeddings[0], (float, int))
                ):
                    return [raw_embeddings]  # Wrap single vector in a list
                else:
                    self._logger.error(
                        f"Unexpected embedding format for single input. Type: {type(raw_embeddings)}"
                    )
                    raise ValueError(
                        "Embedding API returned unexpected format for single input."
                    )
            else:  # Batch input
                if isinstance(raw_embeddings, list) and (
                    not raw_embeddings
                    or all(isinstance(e, list) for e in raw_embeddings)
                ):
                    # If original input list had empty strings filtered, the result matches filtered list length
                    return raw_embeddings
                else:
                    self._logger.error(
                        f"Unexpected embedding format for batch input. Type: {type(raw_embeddings)}"
                    )
                    raise ValueError(
                        "Embedding API returned unexpected format for batch input."
                    )

        except Exception as e:
            self._logger.error(
                f"Error generating embeddings with model {model_to_use}: {e}",
                exc_info=True,
            )
            # Do not update last call time if API call failed
            raise

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        self._wait_for_rate_limit(
            model_rpm=self.rpm_limit
        )  # Use generation model's RPM
        tools = None
        tool_config = None
        if schema:
            try:
                tools = [pydantic_to_google_tool(schema)]
                tool_config = {"function_calling_config": {"mode": "ANY"}}
                self._logger.debug(
                    f"Attempting structured output with schema: {schema.__name__}"
                )
            except Exception as e:
                self._logger.error(
                    f"Failed to convert Pydantic schema {schema.__name__}: {e}",
                    exc_info=True,
                )
                self._logger.warning("Proceeding with standard text generation.")
        try:
            response = self.model.generate_content(
                prompt, tools=tools, tool_config=tool_config
            )
            self._update_last_call_time()

            if schema and response.candidates and response.candidates[0].content.parts:
                function_call_part = next(
                    (
                        p
                        for p in response.candidates[0].content.parts
                        if hasattr(p, "function_call") and p.function_call
                    ),
                    None,
                )
                if function_call_part:
                    fc = function_call_part.function_call
                    self._logger.debug(f"Model returned function call: {fc.name}")
                    if fc.name != schema.__name__:
                        self._logger.warning(
                            f"Model called '{fc.name}', expected '{schema.__name__}'. Parsing anyway."
                        )
                    try:
                        args_dict = dict(fc.args)
                        self._logger.debug(f"Extracted args: {args_dict}")
                        return schema.model_validate(args_dict)
                    except Exception as val_err:
                        self._logger.error(
                            f"Pydantic validation for {schema.__name__} failed: {val_err}",
                            exc_info=True,
                        )
                        self._logger.error(f"Failing args dict: {args_dict if 'args_dict' in locals() else 'not available'}")  # type: ignore
                        return None  # Validation failed
                else:
                    self._logger.warning(
                        f"Schema {schema.__name__} provided, but no function call returned."
                    )
            try:
                text_content = response.text
                if not text_content and (not schema or not function_call_part):  # type: ignore
                    self._logger.warning(
                        "Response has no text (potentially blocked or empty)."
                    )
                    # Log details if available
                    if hasattr(response, "prompt_feedback"):
                        self._logger.debug(
                            f"Prompt feedback: {response.prompt_feedback}"
                        )
                    if response.candidates and hasattr(
                        response.candidates[0], "finish_reason"
                    ):
                        self._logger.debug(
                            f"Finish reason: {response.candidates[0].finish_reason}"
                        )
                    return None
                return text_content
            except ValueError:  # .text raises ValueError if blocked
                self._logger.warning("Response blocked (ValueError accessing .text).")
                if hasattr(response, "prompt_feedback"):
                    self._logger.debug(f"Prompt feedback: {response.prompt_feedback}")
                if response.candidates:
                    self._logger.debug(
                        f"Finish reason: {response.candidates[0].finish_reason}"
                    )
                    self._logger.debug(
                        f"Safety Ratings: {response.candidates[0].safety_ratings}"
                    )
                return None
            except Exception as text_err:
                self._logger.error(
                    f"Error extracting text from response: {text_err}", exc_info=True
                )
                return None
        except Exception as e:
            self._logger.error(f"Error during Gemini API call: {e}", exc_info=True)
            raise


# --- Example Usage ---
def main():
    class MockConfig:  # Simple mock for standalone testing
        LOGGER_NAME = "test_llm_direct"
        LOG_FILE = "test_llm_direct.log"
        GEMINI_LLM_MODEL = "models/gemini-1.5-flash-latest"  # Or "gemini-1.5-flash-001"
        GEMINI_EMBEDDING_MODEL = "models/embedding-001"  # Default embedding model
        # GEMINI_EMBEDDING_MODEL = "models/gemini-embedding-exp-03-07" # For testing experimental

    global cfg
    cfg = MockConfig()  # type: ignore

    logger = Logger()  # Initialize logger early

    if "GENAI_API_KEY" not in os.environ:
        logger.error(
            "GENAI_API_KEY environment variable not set. Please set it to run the example."
        )
        exit(1)

    class TestSchemaDirect(BaseModel):
        numbers_list: List[int] = Field(
            ..., description="A list of 5 different integers."
        )
        comment: Optional[str] = Field(None, description="An optional comment.")

    test_prompt = "Generate a list of 5 distinct integers. Add a short comment."
    texts_to_embed_single = "Hello world, this is a test document."
    texts_to_embed_batch = [
        "The quick brown fox jumps over the lazy dog.",
        "Gemini is a family of generative AI models.",
        "",  # Test empty string in batch
        "This is the third document for embedding.",
    ]

    try:
        logger.info("Initializing Direct API GeminiModel...")
        gemini_model = GeminiModel()  # Uses GEMINI_LLM_MODEL from cfg

        # --- Test Token Count ---
        logger.info("\n--- Testing token count ---")
        count = gemini_model.token_count(test_prompt)
        logger.info(f"Token count for prompt ('{test_prompt[:30]}...'): {count}")

        # --- Test Standard Generation ---
        logger.info("\n--- Testing standard generation ---")
        standard_response = gemini_model.generate(test_prompt)
        logger.info(f"Standard Response: {standard_response}")

        # --- Test Structured Generation ---
        logger.info("\n--- Testing structured generation ---")
        structured_response = gemini_model.generate(
            test_prompt, schema=TestSchemaDirect
        )
        logger.info(f"Structured Response: {structured_response}")
        if isinstance(structured_response, TestSchemaDirect):
            logger.info(
                f"Parsed list: {structured_response.numbers_list}, Comment: {structured_response.comment}"
            )

        # --- Test Embeddings ---
        logger.info("\n--- Testing embeddings ---")

        # Single document embedding
        logger.info(
            f"Embedding single document with default model ('{gemini_model.default_embedding_model}')..."
        )
        single_embedding_result = gemini_model.generate_embeddings(
            texts_to_embed_single
        )
        if single_embedding_result:
            logger.info(
                f"Single embedding vector dimension: {len(single_embedding_result[0])}"
            )
            # logger.info(f"Single embedding vector (first 5 dims): {single_embedding_result[0][:5]}")
        else:
            logger.warning("Single embedding result was empty.")

        # Batch document embedding with a specific task type
        logger.info(f"Embedding batch documents with task 'RETRIEVAL_DOCUMENT'...")
        batch_embedding_result = gemini_model.generate_embeddings(
            texts_to_embed_batch,
            task_type="RETRIEVAL_DOCUMENT",  # Example task type
            # title="Sample Batch Documents" # Example title
            # embedding_model_name="models/gemini-embedding-exp-03-07" # Example override
        )
        if batch_embedding_result:
            logger.info(
                f"Batch embeddings generated for {len(batch_embedding_result)} documents."
            )
            for i, emb in enumerate(batch_embedding_result):
                logger.info(f"  Doc {i} vector dimension: {len(emb)}")
        else:
            logger.warning("Batch embedding result was empty.")

        # Test embedding an empty string
        logger.info("Embedding empty string (should return empty list)...")
        empty_string_emb = gemini_model.generate_embeddings("")
        logger.info(f"Embedding for empty string: {empty_string_emb} (Expected: [])")

        # Test embedding list with only empty string
        logger.info(
            "Embedding list with only empty string (should return empty list)..."
        )
        empty_list_emb = gemini_model.generate_embeddings([""])
        logger.info(
            f"Embedding for list with empty string: {empty_list_emb} (Expected: [])"
        )

    except Exception as e:
        logger.error(f"\nAn error occurred in main: {e}", exc_info=True)


if __name__ == "__main__":
    main()

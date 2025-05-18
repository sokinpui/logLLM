# llm_model_direct_api.py

import json
import os
import time
from typing import Any, Dict, List, Optional, Type, Union

# Google Generative AI API
import google.generativeai as genai
from google.ai.generativelanguage import (
    FunctionDeclaration,
    Schema,
    Tool,
)
from google.ai.generativelanguage import Type as GoogleApiType
from google.generativeai import types as genai_types

# Pydantic related imports
from pydantic import BaseModel, Field

from ..config import config as cfg
from .logger import Logger

try:
    from vertexai.preview import tokenization

    VERTEX_TOKENIZER_AVAILABLE = True
except ImportError:
    VERTEX_TOKENIZER_AVAILABLE = False
    print(
        "Warning: vertexai.preview.tokenization not found. Local token counting will be disabled. "
        "Consider installing google-cloud-aiplatform for this feature."
    )

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
            pass
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
    "models/text-embedding-004": 1500,
    "text-embedding-004": 1500,
    "models/embedding-001": 1500,
    "embedding-001": 1500,
    "models/gemini-embedding-exp-03-07": 5,
    "gemini-embedding-exp-03-07": 5,
    "default": 15,
}

EMBEDDING_MODEL_TOKEN_LIMITS = {
    "models/text-embedding-004": 2048,
    "text-embedding-004": 2048,
    "models/embedding-001": 2048,  # Common limit, adjust if known otherwise
    "embedding-001": 2048,
    "models/gemini-embedding-exp-03-07": 2048,  # Assuming default, adjust if specific limit known
    "gemini-embedding-exp-03-07": 2048,
    "default": 2048,  # Default embedding token limit
}


class LLMModel:
    def __init__(self):
        self._logger = Logger()
        self.model = None
        self.context_size = 0
        self._last_api_call_time: Optional[float] = None
        self.rpm_limit: int = 15
        self.min_request_interval: float = 60.0 / self.rpm_limit

    def _wait_for_rate_limit(self, model_rpm: Optional[int] = None):
        current_rpm_limit = model_rpm or self.rpm_limit
        if current_rpm_limit <= 0:
            return
        min_interval = 60.0 / current_rpm_limit
        if self._last_api_call_time is None:
            return
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


class GeminiModel(LLMModel):
    def __init__(self, model_name: str | None = None):
        super().__init__()
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = cfg.GEMINI_LLM_MODEL

        self.api_model_name_key = self.model_name.split("/")[-1]
        self.rpm_limit = MODEL_RPM_LIMITS.get(
            self.api_model_name_key, MODEL_RPM_LIMITS["default"]
        )

        if self.rpm_limit <= 0:
            self._logger.warning(
                f"RPM limit for generation model {self.model_name} is zero or invalid."
            )
            self.min_request_interval = 0
        else:
            self.min_request_interval = 60.0 / self.rpm_limit

        self.default_embedding_model: str = getattr(
            cfg,
            "GEMINI_EMBEDDING_MODEL",
            "models/text-embedding-004",  # Updated default
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
            os.environ["GOOGLE_API_KEY"] = api_key
            self.generation_config = genai.GenerationConfig(temperature=1.0)
            self.safety_settings = {}
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings,
            )
            self._logger.info(
                f"Generative model {self.model_name} initialized successfully."
            )
            if not VERTEX_TOKENIZER_AVAILABLE:
                self._logger.warning(
                    "vertexai.preview.tokenization not available. Local token counting may be less accurate or slower."
                )
        except Exception as e:
            self._logger.error(
                f"Error initializing google-generativeai: {e}", exc_info=True
            )
            raise

    def token_count(self, prompt: str | None) -> int:
        if prompt is None:
            return 0
        if VERTEX_TOKENIZER_AVAILABLE:
            try:
                # User's code had this hardcoded, using it as a general proxy for chunking estimations.
                tokenizer_model_key = "gemini-1.5-flash-001"
                tokenizer = tokenization.get_tokenizer_for_model(tokenizer_model_key)
                count_response = tokenizer.count_tokens(prompt)
                return count_response.total_tokens
            except Exception as e_vertex:
                self._logger.warning(
                    f"Local token count with vertexai for '{tokenizer_model_key}' failed: {e_vertex}. Falling back."
                )
        try:
            # Fallback to generative model's count_tokens
            count = self.model.count_tokens(prompt).total_tokens
            return count
        except Exception as e_genai:
            self._logger.warning(
                f"API token count with genai for {self.model_name} failed: {e_genai}. Basic estimate."
            )
            return len(prompt.split())  # Basic fallback

    def _average_embeddings(self, embeddings: List[List[float]]) -> List[float]:
        if not embeddings:
            return []
        if len(embeddings) == 1:
            return embeddings[0]

        dim = len(embeddings[0])
        if not all(len(e) == dim for e in embeddings):
            self._logger.error(
                "Cannot average embeddings of different dimensions. Returning first embedding."
            )
            return embeddings[0]

        avg_embedding = [0.0] * dim
        for emb_vector in embeddings:
            for i in range(dim):
                avg_embedding[i] += emb_vector[i]

        num_embeddings = len(embeddings)
        for i in range(dim):
            avg_embedding[i] /= num_embeddings
        return avg_embedding

    def _split_text_into_chunks(
        self, text: str, chunk_token_limit: int, chunk_word_overlap: int = 50
    ) -> List[str]:
        """
        Splits text into chunks, each not exceeding chunk_token_limit.
        Uses self.token_count for estimation. Overlap is in words.
        """
        self._logger.debug(
            f"Attempting to chunk text. Target token limit: {chunk_token_limit}, Word overlap: {chunk_word_overlap}"
        )
        words = text.split()  # Simple whitespace split
        if not words:
            return []

        # If the whole text is already within limit (considering a small buffer for join characters)
        # Buffer helps avoid re-tokenizing if original text is just under the limit.
        if self.token_count(text) < chunk_token_limit - 5:  # 5 is a small buffer
            return [text]

        all_chunks: List[str] = []
        current_chunk_words: List[str] = []

        idx = 0
        while idx < len(words):
            word_to_add = words[idx]

            # Try adding the word
            potential_new_chunk_words = current_chunk_words + [word_to_add]
            potential_new_chunk_str = " ".join(potential_new_chunk_words)
            estimated_tokens = self.token_count(potential_new_chunk_str)

            if estimated_tokens < chunk_token_limit:
                current_chunk_words.append(word_to_add)
                idx += 1
            else:
                # Word makes it too long. Finalize the current_chunk_words (if any).
                if current_chunk_words:
                    all_chunks.append(" ".join(current_chunk_words))

                    # Determine overlap for the next chunk from the just finalized one.
                    overlap_start_idx = max(
                        0, len(current_chunk_words) - chunk_word_overlap
                    )
                    new_current_chunk_words = current_chunk_words[overlap_start_idx:]

                    # If the word_to_add itself made current_chunk_words (which was empty) too long
                    if not all_chunks or " ".join(new_current_chunk_words) != " ".join(
                        current_chunk_words
                    ):  # check if it made progress
                        current_chunk_words = new_current_chunk_words
                    else:  # single word is too long or overlap is not helping
                        current_chunk_words = (
                            []
                        )  # Reset, word_to_add will start a new chunk or be a chunk itself

                    # If current_chunk_words after overlap processing ALREADY contains word_to_add (because of how idx is handled or if overlap is large)
                    # we need to ensure word_to_add isn't processed twice or skipped.
                    # The current word (words[idx]) has not been added to a *finalized* chunk yet.
                    # It will be the first candidate for the *new* current_chunk_words.

                elif not current_chunk_words:  # First word itself is too long
                    self._logger.warning(
                        f"Word '{word_to_add[:50]}...' (tokens: {estimated_tokens}) "
                        f"alone exceeds limit {chunk_token_limit}. Adding as its own chunk."
                    )
                    all_chunks.append(word_to_add)  # Add it as a chunk
                    current_chunk_words = []  # Reset for next
                    idx += 1  # Move to next word

            # If at the end, add remaining current_chunk_words
            if idx == len(words):
                if current_chunk_words:
                    all_chunks.append(" ".join(current_chunk_words))
                break

        return all_chunks if all_chunks else ([text] if text else [])

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
        token_limit = EMBEDDING_MODEL_TOKEN_LIMITS.get(
            embedding_model_key, EMBEDDING_MODEL_TOKEN_LIMITS["default"]
        )

        self._wait_for_rate_limit(model_rpm=embedding_rpm)

        original_input_list: List[str] = [contents] if isinstance(contents, str) else contents  # type: ignore

        all_texts_for_api: List[str] = []
        # Stores how many API embeddings correspond to each original input text that was non-empty
        num_api_embeddings_per_valid_original_text: List[int] = []
        original_text_was_valid: List[bool] = (
            []
        )  # Tracks if original text was non-empty

        for text_item in original_input_list:
            if (
                not text_item.strip()
            ):  # Consider empty or whitespace-only as invalid for embedding
                original_text_was_valid.append(False)
                continue  # Will result in an empty list [] for this item in the final output

            original_text_was_valid.append(True)
            estimated_tokens = self.token_count(text_item)

            if estimated_tokens > token_limit:
                self._logger.info(
                    f"Text item (approx {estimated_tokens} tokens) for model '{model_to_use}' "
                    f"exceeds limit ({token_limit}). Chunking..."
                )
                # A simple overlap could be 10% of chunk_token_limit, converted to words.
                # For word_overlap_count in _split_text_into_chunks, using a fixed word count for simplicity.
                # e.g., 50 words overlap. Adjust as needed.
                chunks = self._split_text_into_chunks(
                    text_item, token_limit, chunk_word_overlap=30
                )

                if chunks:
                    all_texts_for_api.extend(chunks)
                    num_api_embeddings_per_valid_original_text.append(len(chunks))
                else:  # Chunking failed to produce anything
                    self._logger.warning(
                        f"Chunking returned no result for text: '{text_item[:100]}...'. Sending original (may fail)."
                    )
                    all_texts_for_api.append(text_item)
                    num_api_embeddings_per_valid_original_text.append(1)
            else:
                all_texts_for_api.append(text_item)
                num_api_embeddings_per_valid_original_text.append(1)

        if not all_texts_for_api:
            self._logger.info(
                "No non-empty texts to embed after processing and chunking."
            )
            return [[] for _ in original_input_list]  # Return list of empty lists

        try:
            self._logger.info(
                f"Requesting {len(all_texts_for_api)} embeddings from API for model {model_to_use}."
            )
            response: genai_types.EmbedContentResponse = genai.embed_content(
                model=model_to_use,
                content=all_texts_for_api,
                task_type=task_type,  # type: ignore
                title=title,
                output_dimensionality=output_dimensionality,
            )
            self._update_last_call_time()
            api_response_embeddings = response["embedding"]  # This is List[List[float]]

            if len(api_response_embeddings) != len(all_texts_for_api):
                self._logger.error(
                    f"API returned {len(api_response_embeddings)} embeddings, "
                    f"but {len(all_texts_for_api)} were expected. Result mapping may be incorrect."
                )
                # Attempt to pad or truncate, or raise error. For now, proceed with caution.
                # This case indicates a significant issue with API response or assumptions.
                # Fallback: try to construct what we can, or return error state.
                # For simplicity, if this happens, subsequent averaging may fail or be misaligned.

            final_results: List[List[float]] = []
            current_api_emb_idx = 0
            valid_text_idx = (
                0  # To iterate through num_api_embeddings_per_valid_original_text
            )

            for was_valid in original_text_was_valid:
                if not was_valid:
                    final_results.append([])  # For original empty/whitespace strings
                else:
                    if valid_text_idx >= len(
                        num_api_embeddings_per_valid_original_text
                    ):
                        self._logger.error(
                            "Logic error: Ran out of chunk counts for valid texts."
                        )
                        final_results.append([])  # Error case
                        continue

                    num_chunks_for_this_item = (
                        num_api_embeddings_per_valid_original_text[valid_text_idx]
                    )

                    if current_api_emb_idx + num_chunks_for_this_item > len(
                        api_response_embeddings
                    ):
                        self._logger.error(
                            f"Not enough embeddings from API to process item. Needed {num_chunks_for_this_item}, "
                            f"have {len(api_response_embeddings) - current_api_emb_idx} left. Original text index related to {valid_text_idx}."
                        )
                        final_results.append([])  # Error case for this item
                        # Attempt to advance current_api_emb_idx to prevent infinite loop on next items, though data is lost.
                        current_api_emb_idx = min(
                            current_api_emb_idx + num_chunks_for_this_item,
                            len(api_response_embeddings),
                        )
                        valid_text_idx += 1
                        continue

                    if (
                        num_chunks_for_this_item == 0
                    ):  # Should not happen if was_valid is true and it wasn't chunked into nothing
                        final_results.append([])
                    elif num_chunks_for_this_item == 1:
                        final_results.append(
                            api_response_embeddings[current_api_emb_idx]
                        )
                    else:  # Averaging needed
                        embeddings_to_average = api_response_embeddings[
                            current_api_emb_idx : current_api_emb_idx
                            + num_chunks_for_this_item
                        ]
                        averaged_embedding = self._average_embeddings(
                            embeddings_to_average
                        )
                        final_results.append(averaged_embedding)

                    current_api_emb_idx += num_chunks_for_this_item
                    valid_text_idx += 1

            return final_results

        except Exception as e:
            self._logger.error(
                f"Error generating embeddings with model {model_to_use}: {e}",
                exc_info=True,
            )
            raise

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None):
        self._wait_for_rate_limit(model_rpm=self.rpm_limit)
        tools = None
        tool_config = None
        if schema:
            try:
                tools = [pydantic_to_google_tool(schema)]
                tool_config = {"function_calling_config": {"mode": "ANY"}}
                self._logger.debug(f"Attempting structured output: {schema.__name__}")
            except Exception as e:
                self._logger.error(
                    f"Pydantic schema conversion error: {e}", exc_info=True
                )
                self._logger.warning("Proceeding with standard text generation.")
        try:
            response = self.model.generate_content(
                prompt, tools=tools, tool_config=tool_config
            )
            self._update_last_call_time()
            if schema and response.candidates and response.candidates[0].content.parts:
                fc_part = next(
                    (
                        p
                        for p in response.candidates[0].content.parts
                        if hasattr(p, "function_call") and p.function_call
                    ),
                    None,
                )
                if fc_part:
                    fc = fc_part.function_call
                    self._logger.debug(f"Model returned function call: {fc.name}")
                    if fc.name != schema.__name__:
                        self._logger.warning(
                            f"Expected '{schema.__name__}', got '{fc.name}'."
                        )
                    try:
                        args_dict = dict(fc.args)
                        return schema.model_validate(args_dict)
                    except Exception as val_err:
                        self._logger.error(
                            f"Pydantic validation failed: {val_err}", exc_info=True
                        )
                        return None
                else:
                    self._logger.warning(
                        f"Schema provided but no function call in response."
                    )
            try:
                text_content = response.text
                if not text_content and (not schema or not fc_part):  # type: ignore
                    self._logger.warning("Response empty/blocked.")
                    return None
                return text_content
            except ValueError:
                self._logger.warning("Response blocked (ValueError accessing .text).")
                return None
            except Exception as text_err:
                self._logger.error(f"Error extracting text: {text_err}", exc_info=True)
                return None
        except Exception as e:
            self._logger.error(f"Gemini API call error: {e}", exc_info=True)
            raise


def main():
    class MockConfig:
        LOGGER_NAME = "test_llm_direct"
        LOG_FILE = "test_llm_direct.log"
        GEMINI_LLM_MODEL = "models/gemini-1.5-flash-latest"
        GEMINI_EMBEDDING_MODEL = (
            "models/text-embedding-004"  # Uses a model with known limits
        )

    global cfg
    cfg = MockConfig()  # type: ignore
    logger = Logger()

    if "GENAI_API_KEY" not in os.environ:
        logger.error("GENAI_API_KEY environment variable not set.")
        exit(1)

    gemini_model = GeminiModel()

    long_text_parts = [
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "This is the first part of a very long story that needs to be chunked for embedding. It talks about many things, including coding, AI, and the future.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
        "The story continues, describing adventures in digital realms and the challenges of creating intelligent systems. It has to be long enough to trigger chunking.",
        "More details are added, with complex characters and intricate plots unfolding. Each sentence adds to the token count, pushing it towards the limit.",
        "And yet more text to ensure it's quite long. We need several hundred words at least. Let's repeat some phrases for good measure. The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.",
        "The tale goes on, with more and more details, pushing the boundaries of the embedding model's capacity for a single input. This should definitely be over 200-300 tokens.",
        "Final segment to make it very long indeed. The goal is to test the chunking mechanism and ensure that the embeddings are still produced and averaged correctly.",
    ]
    very_long_text = " ".join(long_text_parts) * 3  # Make it quite long

    short_text1 = "This is a short text."
    short_text2 = "Another brief document."
    empty_text = ""

    texts_to_embed_batch = [short_text1, very_long_text, short_text2, empty_text]

    logger.info(
        f"Token count for very_long_text (approx using gen model tokenizer): {gemini_model.token_count(very_long_text)}"
    )

    try:
        logger.info("\n--- Testing embeddings with chunking ---")
        batch_embedding_result = gemini_model.generate_embeddings(
            texts_to_embed_batch, task_type="RETRIEVAL_DOCUMENT"
        )
        if batch_embedding_result:
            logger.info(
                f"Batch embeddings generated. Results count: {len(batch_embedding_result)}"
            )
            for i, emb_list in enumerate(batch_embedding_result):
                original_text_preview = (
                    texts_to_embed_batch[i][:50].replace("\n", " ") + "..."
                    if texts_to_embed_batch[i]
                    else "[EMPTY STRING]"
                )
                if emb_list:  # Non-empty list of floats
                    logger.info(
                        f"  Original text {i} ('{original_text_preview}'): Embedding dim {len(emb_list)}"
                    )
                else:  # Empty list, means original was empty or error
                    logger.info(
                        f"  Original text {i} ('{original_text_preview}'): No embedding generated (empty list)."
                    )
        else:
            logger.warning("Batch embedding result was None or empty list itself.")

        logger.info("\n--- Testing single long text embedding ---")
        single_long_embedding = gemini_model.generate_embeddings(very_long_text)
        if single_long_embedding and single_long_embedding[0]:
            logger.info(
                f"Single long text embedding dim: {len(single_long_embedding[0])}"
            )
        else:
            logger.warning("Single long text embedding failed or returned empty.")

    except Exception as e:
        logger.error(f"\nAn error occurred in main: {e}", exc_info=True)


if __name__ == "__main__":
    main()

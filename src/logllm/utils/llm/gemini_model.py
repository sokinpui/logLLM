# logllm/utils/llm_models/gemini_model.py
import json
import os
import time
from typing import Any, Dict, List, Optional, Type, Union

import google.generativeai as genai
from google.ai.generativelanguage import FunctionDeclaration, Schema, Tool
from google.ai.generativelanguage import Type as GoogleApiType
from google.generativeai import types as genai_types
from pydantic import BaseModel

from ...config import config as cfg
from ...mcp.schemas import (
    ContextPayload,
    MCPToolCall,
    MCPToolDefinition,
    MCPToolParameterSchema,
)
from ..logger import Logger
from .llm_abc import LLMModel

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
    "models/embedding-001": 2048,
    "embedding-001": 2048,
    "models/gemini-embedding-exp-03-07": 2048,
    "gemini-embedding-exp-03-07": 2048,
    "default": 2048,
}


class GeminiModel(LLMModel):
    def __init__(self, model_name: str | None = None):
        super().__init__()
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = cfg.GEMINI_LLM_MODEL

        self._last_api_call_time: Optional[float] = None
        self.api_model_name_key = self.model_name.split("/")[-1]
        self.rpm_limit = MODEL_RPM_LIMITS.get(
            self.api_model_name_key, MODEL_RPM_LIMITS["default"]
        )

        if self.rpm_limit <= 0:
            self._logger.warning(
                f"RPM limit for generation model {self.model_name} is zero or invalid. Rate limiting might be ineffective."
            )
        self.default_embedding_model: str = getattr(
            cfg, "GEMINI_EMBEDDING_MODEL", "models/text-embedding-004"
        )
        self._logger.info(
            f"Initialized Direct API GeminiModel: {self.model_name} (Generation RPM: {self.rpm_limit}). "
            f"Default embedding model: {self.default_embedding_model}."
        )

        api_key = os.environ.get("GENAI_API_KEY")
        if api_key is None:
            self._logger.error("GENAI_API_KEY environment variable not set.")
            raise ValueError("GENAI_API_KEY environment variable not set.")

        try:
            genai.configure(api_key=api_key)
            os.environ["GOOGLE_API_KEY"] = api_key
            self.generation_config = genai.GenerationConfig(temperature=0.7)
            self.safety_settings = {}
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings,
            )
            if "flash" in self.model_name:
                self.context_size = 128000
            elif "pro" in self.model_name:
                self.context_size = 1000000
            else:
                self.context_size = 32000

            self._logger.info(
                f"Generative model {self.model_name} initialized successfully. Estimated context size: {self.context_size} tokens."
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

    def token_count(self, text_content: Optional[str]) -> int:
        if text_content is None:
            return 0
        if VERTEX_TOKENIZER_AVAILABLE:
            try:
                tokenizer_model_key = "gemini-1.5-flash-001"
                tokenizer = tokenization.get_tokenizer_for_model(tokenizer_model_key)
                count_response = tokenizer.count_tokens(text_content)
                return count_response.total_tokens
            except Exception as e_vertex:
                self._logger.warning(
                    f"Local token count with vertexai for '{tokenizer_model_key}' failed: {e_vertex}. Falling back to API count."
                )
        try:
            count = self.model.count_tokens(text_content).total_tokens
            return count
        except Exception as e_genai:
            self._logger.warning(
                f"API token count with genai for {self.model_name} failed: {e_genai}. Falling back to basic word count."
            )
            return len(text_content.split())

    def _mcp_tool_definitions_to_gemini_tools(
        self, mcp_tools: List[MCPToolDefinition]
    ) -> List[Tool]:
        gemini_tools: List[Tool] = []
        for mcp_tool_def in mcp_tools:
            google_properties: Dict[str, Schema] = {}
            required_params: List[str] = []

            if mcp_tool_def.parameters:
                for name, param_schema in mcp_tool_def.parameters.items():
                    google_type = TYPE_MAP.get(
                        param_schema.type, GoogleApiType.TYPE_UNSPECIFIED
                    )
                    items_schema_for_google = None
                    if param_schema.type == "array" and param_schema.items:
                        item_type_str = param_schema.items.get("type", "string")
                        item_google_type = TYPE_MAP.get(
                            item_type_str, GoogleApiType.STRING
                        )
                        items_schema_for_google = Schema(
                            type=item_google_type,
                            description=param_schema.items.get("description"),
                        )
                    google_properties[name] = Schema(
                        type=google_type,
                        description=param_schema.description,
                        enum=param_schema.enum,
                        items=items_schema_for_google,
                    )
                    if param_schema.required:
                        required_params.append(name)

            func_decl = FunctionDeclaration(
                name=mcp_tool_def.name,
                description=mcp_tool_def.description,
                parameters=Schema(
                    type=GoogleApiType.OBJECT,
                    properties=google_properties,
                    required=(required_params if required_params else None),
                ),
            )
            gemini_tools.append(Tool(function_declarations=[func_decl]))
        return gemini_tools

    def generate(
        self,
        prompt_content: Union[str, ContextPayload],
        output_schema: Optional[Type[BaseModel]] = None,
        tools: Optional[List[MCPToolDefinition]] = None,
    ) -> Union[str, BaseModel, MCPToolCall, None]:
        self._wait_for_rate_limit(model_rpm=self.rpm_limit)

        if isinstance(prompt_content, ContextPayload):
            from ...mcp.mcp_manager import ContextManager

            context_manager = ContextManager(logger=self._logger)
            prompt_str = context_manager.format_payload_for_llm_prompt(prompt_content)
        else:
            prompt_str = prompt_content

        gemini_tools_list: Optional[List[Tool]] = None
        tool_config_dict: Optional[Dict[str, Any]] = None

        if output_schema:
            try:
                gemini_tools_list = [pydantic_to_google_tool(output_schema)]
                tool_config_dict = {"function_calling_config": {"mode": "ANY"}}
                self._logger.debug(
                    f"LLM call configured for structured output via Pydantic schema: {output_schema.__name__}"
                )
            except Exception as e:
                self._logger.error(
                    f"Error converting Pydantic schema '{output_schema.__name__}' to Gemini tool: {e}",
                    exc_info=True,
                )
                output_schema = None
        elif tools:
            try:
                gemini_tools_list = self._mcp_tool_definitions_to_gemini_tools(tools)
                tool_config_dict = {"function_calling_config": {"mode": "ANY"}}
                self._logger.debug(
                    f"LLM call configured with {len(gemini_tools_list)} MCP tools."
                )
            except Exception as e:
                self._logger.error(
                    f"Error converting MCPToolDefinitions to Gemini tools: {e}",
                    exc_info=True,
                )
                tools = None

        try:
            self._logger.debug(
                f"Generating content with model '{self.model_name}'. Prompt (first 200 chars): '{prompt_str[:200]}...'"
            )
            response = self.model.generate_content(
                prompt_str,
                tools=gemini_tools_list,
                tool_config=tool_config_dict,
            )
            self._update_last_call_time()

            if response.candidates and response.candidates[0].content.parts:
                function_call_part = next(
                    (
                        p
                        for p in response.candidates[0].content.parts
                        if hasattr(p, "function_call") and p.function_call
                    ),
                    None,
                )

                if function_call_part:
                    gemini_fc = function_call_part.function_call
                    self._logger.info(
                        f"Model returned function call: Name='{gemini_fc.name}', Args='{dict(gemini_fc.args)}'"
                    )

                    if output_schema and gemini_fc.name == output_schema.__name__:
                        try:
                            validated_output = output_schema.model_validate(
                                dict(gemini_fc.args)
                            )
                            return validated_output
                        except Exception as val_err:
                            self._logger.error(
                                f"Pydantic validation failed for schema '{output_schema.__name__}': {val_err}",
                                exc_info=True,
                            )
                            try:
                                return response.text
                            except:
                                return None
                    elif tools:
                        mcp_tool_call = MCPToolCall(
                            tool_name=gemini_fc.name, arguments=dict(gemini_fc.args)
                        )
                        return mcp_tool_call
                    else:
                        self._logger.warning(
                            f"Model returned an unexpected function call '{gemini_fc.name}'."
                        )
                        try:
                            return response.text
                        except:
                            return None
            try:
                text_content = response.text
                if not text_content:
                    self._logger.warning(
                        "LLM response.text is empty. This might indicate blocked content."
                    )
                    if response.prompt_feedback:
                        self._logger.warning(
                            f"Prompt Feedback: {response.prompt_feedback}"
                        )
                    return None
                return text_content
            except ValueError:
                self._logger.warning(
                    "Accessing response.text failed (ValueError), likely due to blocked content."
                )
                if response.prompt_feedback:
                    self._logger.warning(f"Prompt Feedback: {response.prompt_feedback}")
                return None
            except Exception as text_err:
                self._logger.error(
                    f"Error extracting text content from LLM response: {text_err}",
                    exc_info=True,
                )
                return None

        except Exception as e:
            self._logger.error(f"Gemini API call error: {e}", exc_info=True)
            raise

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
        self._logger.debug(
            f"Attempting to chunk text. Target token limit: {chunk_token_limit}, Word overlap: {chunk_word_overlap}"
        )
        words = text.split()
        if not words:
            return []

        if self.token_count(text) < chunk_token_limit - 5:
            return [text]

        all_chunks: List[str] = []
        current_chunk_words: List[str] = []
        idx = 0
        while idx < len(words):
            word_to_add = words[idx]
            potential_new_chunk_words = current_chunk_words + [word_to_add]
            potential_new_chunk_str = " ".join(potential_new_chunk_words)
            estimated_tokens = self.token_count(potential_new_chunk_str)

            if estimated_tokens < chunk_token_limit:
                current_chunk_words.append(word_to_add)
                idx += 1
            else:
                if current_chunk_words:
                    all_chunks.append(" ".join(current_chunk_words))
                    overlap_start_idx = max(
                        0, len(current_chunk_words) - chunk_word_overlap
                    )
                    new_current_chunk_words = current_chunk_words[overlap_start_idx:]
                    if not all_chunks or " ".join(new_current_chunk_words) != " ".join(
                        current_chunk_words
                    ):
                        current_chunk_words = new_current_chunk_words
                    else:
                        current_chunk_words = []
                elif not current_chunk_words:
                    self._logger.warning(
                        f"Word '{word_to_add[:50]}...' (tokens: {estimated_tokens}) "
                        f"alone exceeds limit {chunk_token_limit}. Adding as its own chunk."
                    )
                    all_chunks.append(word_to_add)
                    current_chunk_words = []
                    idx += 1
            if idx == len(words):
                if current_chunk_words:
                    all_chunks.append(" ".join(current_chunk_words))
                break
        return all_chunks if all_chunks else ([text] if text else [])

    def generate_embeddings(
        self,
        contents: Union[str, List[str]],
        embedding_model_name: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        model_to_use = embedding_model_name or self.default_embedding_model
        embedding_model_key = model_to_use.split("/")[-1]
        embedding_rpm = MODEL_RPM_LIMITS.get(
            embedding_model_key, MODEL_RPM_LIMITS["default"]
        )
        token_limit_for_embedding_model = EMBEDDING_MODEL_TOKEN_LIMITS.get(
            embedding_model_key, EMBEDDING_MODEL_TOKEN_LIMITS["default"]
        )

        self._wait_for_rate_limit(model_rpm=embedding_rpm)

        input_texts: List[str] = [contents] if isinstance(contents, str) else contents
        original_text_is_valid: List[bool] = [
            bool(text and text.strip()) for text in input_texts
        ]

        api_texts: List[str] = []
        num_api_embeddings_per_valid_original_text: List[int] = []

        for i, text_item in enumerate(input_texts):
            if not original_text_is_valid[i]:
                continue
            estimated_tokens = self.token_count(text_item)
            if estimated_tokens > token_limit_for_embedding_model:
                self._logger.info(
                    f"Text item for embedding model '{model_to_use}' (approx {estimated_tokens} tokens) "
                    f"exceeds its limit ({token_limit_for_embedding_model}). Chunking..."
                )
                chunks = self._split_text_into_chunks(
                    text_item, token_limit_for_embedding_model, chunk_word_overlap=30
                )
                if chunks:
                    api_texts.extend(chunks)
                    num_api_embeddings_per_valid_original_text.append(len(chunks))
                else:
                    self._logger.warning(
                        f"Chunking failed for text: '{text_item[:100]}...'. Sending original."
                    )
                    api_texts.append(text_item)
                    num_api_embeddings_per_valid_original_text.append(1)
            else:
                api_texts.append(text_item)
                num_api_embeddings_per_valid_original_text.append(1)

        if not api_texts:
            self._logger.info("No valid texts to embed after processing.")
            return [[] for _ in input_texts]

        try:
            self._logger.info(
                f"Requesting {len(api_texts)} embeddings from API for model '{model_to_use}'. Task type: {kwargs.get('task_type', 'N/A')}."
            )
            response: genai_types.EmbedContentResponse = genai.embed_content(
                model=model_to_use, content=api_texts, **kwargs
            )
            self._update_last_call_time()
            api_response_embeddings: List[List[float]] = response["embedding"]

            if len(api_response_embeddings) != len(api_texts):
                self._logger.error(
                    f"API returned {len(api_response_embeddings)} embeddings, but {len(api_texts)} were expected."
                )
            final_embeddings_list: List[List[float]] = []
            api_emb_idx = 0
            valid_original_text_chunk_counts_iter = iter(
                num_api_embeddings_per_valid_original_text
            )
            for is_valid in original_text_is_valid:
                if not is_valid:
                    final_embeddings_list.append([])
                    continue
                try:
                    num_chunks_for_this = next(valid_original_text_chunk_counts_iter)
                except StopIteration:
                    self._logger.error(
                        "Logic error: Mismatch in tracking valid texts and their chunk counts."
                    )
                    final_embeddings_list.append([])
                    continue
                if api_emb_idx + num_chunks_for_this > len(api_response_embeddings):
                    self._logger.error(
                        f"Not enough embeddings from API for current item. Expected {num_chunks_for_this}, available {len(api_response_embeddings) - api_emb_idx}."
                    )
                    final_embeddings_list.append([])
                    api_emb_idx = len(api_response_embeddings)
                    continue
                if num_chunks_for_this == 0:
                    final_embeddings_list.append([])
                elif num_chunks_for_this == 1:
                    final_embeddings_list.append(api_response_embeddings[api_emb_idx])
                else:
                    chunked_embeddings = api_response_embeddings[
                        api_emb_idx : api_emb_idx + num_chunks_for_this
                    ]
                    final_embeddings_list.append(
                        self._average_embeddings(chunked_embeddings)
                    )
                api_emb_idx += num_chunks_for_this
            return final_embeddings_list
        except Exception as e:
            self._logger.error(
                f"Error generating embeddings with model '{model_to_use}': {e}",
                exc_info=True,
            )
            return [[] for _ in input_texts]


if __name__ == "__main__":
    # Example usage
    model = GeminiModel()
    text = "This is a test prompt for the Gemini model."
    print(model.generate(text))
    print(model.token_count(text))
    print(model.generate_embeddings(text))

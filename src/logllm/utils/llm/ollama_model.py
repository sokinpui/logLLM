# src/logllm/utils/llm/ollama_model.py
import json
from typing import Any, Dict, List, Optional, Type, Union

import ollama
from pydantic import BaseModel, ValidationError

from ...mcp.schemas import (
    ContextPayload,
    MCPToolCall,
    MCPToolDefinition,
)
from ..logger import Logger
from .llm_abc import LLMModel


class OllamaModel(LLMModel):
    """
    LLMModel implementation for interacting with models served by Ollama.
    """

    def __init__(
        self,
        model_name: str = "llama3",
        embedding_model_name: Optional[str] = None,
        ollama_host: Optional[str] = None,
    ):
        super().__init__()
        self.model_name = model_name
        self.embedding_model_name = embedding_model_name or model_name
        self._logger.info(
            f"Initializing OllamaModel. Generation: '{self.model_name}', Embedding: '{self.embedding_model_name}'"
        )
        try:
            self.client = ollama.Client(host=ollama_host)
            self.client.list()
        except Exception as e:
            self._logger.error(
                f"Failed to connect to Ollama. Please ensure Ollama is running. Error: {e}"
            )
            raise ConnectionError("Could not connect to Ollama server.") from e

        # Context size is highly model-dependent, set a reasonable default.
        self.context_size = 4096

    def _mcp_tool_definitions_to_ollama_tools(
        self, mcp_tools: List[MCPToolDefinition]
    ) -> List[Dict[str, Any]]:
        ollama_tools = []
        for mcp_tool in mcp_tools:
            tool_dict = {
                "type": "function",
                "function": {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description,
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
            if mcp_tool.parameters:
                properties = {}
                required = []
                for name, param_schema in mcp_tool.parameters.items():
                    properties[name] = {
                        "type": param_schema.type,
                        "description": param_schema.description,
                    }
                    if param_schema.enum:
                        properties[name]["enum"] = param_schema.enum
                    if param_schema.required:
                        required.append(name)
                tool_dict["function"]["parameters"]["properties"] = properties
                if required:
                    tool_dict["function"]["parameters"]["required"] = required
            ollama_tools.append(tool_dict)
        return ollama_tools

    def generate(
        self,
        prompt_content: Union[str, ContextPayload],
        output_schema: Optional[Type[BaseModel]] = None,
        tools: Optional[List[MCPToolDefinition]] = None,
    ) -> Union[str, BaseModel, MCPToolCall, None]:
        if isinstance(prompt_content, ContextPayload):
            from ...mcp.mcp_manager import ContextManager

            context_manager = ContextManager(logger=self._logger)
            prompt_str = context_manager.format_payload_for_llm_prompt(prompt_content)
        else:
            prompt_str = prompt_content

        messages = [{"role": "user", "content": prompt_str}]
        request_options = {}
        ollama_tools_list = []

        if output_schema:
            request_options["format"] = "json"
        elif tools:
            ollama_tools_list = self._mcp_tool_definitions_to_ollama_tools(tools)

        try:
            self._logger.debug(
                f"Generating content with Ollama model '{self.model_name}'. Format: {request_options.get('format', 'text')}"
            )
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                tools=ollama_tools_list if ollama_tools_list else None,
                options=request_options if request_options else None,
            )

            response_message = response.get("message", {})

            # Handle tool calls
            if response_message.get("tool_calls"):
                tool_call_data = response_message["tool_calls"][0]  # Assuming one call
                function_data = tool_call_data.get("function", {})
                tool_name = function_data.get("name")
                arguments = function_data.get("arguments", {})
                self._logger.info(
                    f"Ollama model returned tool call: {tool_name} with args {arguments}"
                )
                return MCPToolCall(tool_name=tool_name, arguments=arguments)

            content = response_message.get("content", "")
            if not content:
                self._logger.warning("Ollama response content is empty.")
                return None

            if output_schema:
                try:
                    validated_output = output_schema.model_validate_json(content)
                    return validated_output
                except ValidationError as e:
                    self._logger.error(
                        f"Failed to validate Ollama JSON output against schema '{output_schema.__name__}': {e}"
                    )
                    return None
            return content

        except Exception as e:
            self._logger.error(f"Ollama API call error: {e}", exc_info=True)
            return None

    def token_count(self, text_content: Optional[str]) -> int:
        if not text_content:
            return 0
        # Ollama python library does not have a built-in tokenizer.
        # A simple word count is used as a fallback. For higher accuracy,
        # consider using a library like `tiktoken` with a tokenizer appropriate
        # for the model family you are using (e.g., Llama, Mistral).
        count = len(text_content.split())
        self._logger.debug(f"Estimated token count using word count: {count}")
        return count

    def generate_embeddings(
        self,
        contents: Union[str, List[str]],
        embedding_model_name: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        model_to_use = embedding_model_name or self.embedding_model_name
        input_texts = [contents] if isinstance(contents, str) else contents
        final_embeddings: List[List[float]] = []

        # Ollama's embedding endpoint can take a list of prompts.
        # We process one by one to handle potential errors gracefully.
        for text in input_texts:
            if not text or not text.strip():
                final_embeddings.append([])
                continue
            try:
                self._logger.debug(
                    f"Generating embedding for text with Ollama model '{model_to_use}'..."
                )
                response = self.client.embeddings(model=model_to_use, prompt=text)
                final_embeddings.append(response.get("embedding", []))
            except Exception as e:
                self._logger.error(
                    f"Error generating embedding with Ollama model '{model_to_use}': {e}",
                    exc_info=True,
                )
                final_embeddings.append([])

        return final_embeddings

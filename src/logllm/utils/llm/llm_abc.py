# logllm/utils/llm_models/llm_model_abc.py
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, Union

from pydantic import BaseModel

from ...mcp.schemas import (
    ContextPayload,
    MCPToolCall,
    MCPToolDefinition,
)
from ..logger import Logger


class LLMModel(ABC):
    """Abstract Base Class for all LLM models."""

    def __init__(self):
        self._logger = Logger()
        self.model: Any = None
        self.context_size: int = 0
        self.model_name: str = "undefined_llm_model"

    @abstractmethod
    def generate(
        self,
        prompt_content: Union[str, ContextPayload],
        output_schema: Optional[Type[BaseModel]] = None,
        tools: Optional[List[MCPToolDefinition]] = None,
    ) -> Union[str, BaseModel, MCPToolCall, None]:
        """
        Generates content from the model. Can be a simple text response, a structured
        Pydantic object, or a tool call.
        """
        raise NotImplementedError

    @abstractmethod
    def token_count(self, text_content: Optional[str]) -> int:
        """
        Counts the number of tokens in a given text string according to the model's tokenizer.
        """
        raise NotImplementedError

    @abstractmethod
    def generate_embeddings(
        self,
        contents: Union[str, List[str]],
        embedding_model_name: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        """
        Generates embeddings for a string or list of strings.
        """
        raise NotImplementedError

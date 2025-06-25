# src/logllm/mcp/mcp_manager.py
from typing import List, Any, Optional, Union, Dict

from .schemas import (
    ContextItem,
    ContextPayload,
    ContextMetadata,
    ContextItemType,
    MCPToolDefinition,
    MCPToolCall,
    MCPToolResult,
)
from ..utils.logger import Logger


class ContextManager:
    """
    Manages the creation and assembly of context items and payloads for MCP.
    Future enhancements could include context storage, retrieval, and validation.
    """

    def __init__(self, logger: Optional[Logger] = None):
        self._logger = logger or Logger()

    def create_context_item(
        self,
        type: Union[ContextItemType, str],
        data: Any,
        source_component: Optional[str] = None,
        tags: Optional[List[str]] = None,
        relevance_score: Optional[float] = None,
        related_item_ids: Optional[List[str]] = None,
        item_id: Optional[
            str
        ] = None,  # Allow providing an ID, e.g., if from external source
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextItem:
        """
        Creates a new ContextItem.
        """
        metadata_dict = {
            "source_component": source_component,
            "tags": tags or [],
            "relevance_score": relevance_score,
            "related_item_ids": related_item_ids or [],
        }
        if custom_metadata:
            metadata_dict.update(custom_metadata)

        context_item_args = {
            "type": type,
            "data": data,
            "metadata": ContextMetadata(**metadata_dict),
        }
        if item_id:
            context_item_args["id"] = item_id

        return ContextItem(**context_item_args)  # type: ignore

    def build_context_payload(
        self,
        items: List[ContextItem],
        payload_metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextPayload:
        """
        Builds a ContextPayload from a list of ContextItems.
        """
        return ContextPayload(items=items, payload_metadata=payload_metadata)

    def format_payload_for_llm_prompt(
        self,
        payload: ContextPayload,
        max_items: Optional[int] = None,
        item_separator: str = "\n\n---\n\n",
    ) -> str:
        """
        Formats a ContextPayload into a string suitable for inclusion in an LLM prompt.
        This is a basic formatter; more sophisticated formatting might be needed based on LLM and task.
        Sorts by timestamp (most recent first) if not otherwise specified.
        """
        if not payload.items:
            return ""

        # Sort items by timestamp (descending) and optionally limit
        sorted_items = sorted(
            payload.items, key=lambda item: item.timestamp, reverse=True
        )
        if max_items is not None and max_items > 0:
            sorted_items = sorted_items[:max_items]

        formatted_parts: List[str] = []
        for item in sorted_items:
            part = f"Context Type: {item.type}\n"
            part += f"Timestamp: {item.timestamp.isoformat()}\n"
            if item.metadata.source_component:
                part += f"Source: {item.metadata.source_component}\n"
            if item.metadata.tags:
                part += f"Tags: {', '.join(item.metadata.tags)}\n"

            # Basic data formatting
            if isinstance(item.data, str):
                part += f"Data:\n{item.data}"
            elif isinstance(item.data, (dict, list)):
                try:
                    import json

                    part += (
                        f"Data (JSON):\n{json.dumps(item.data, indent=2, default=str)}"
                    )
                except TypeError:
                    part += f"Data (Object):\n{str(item.data)}"  # Fallback
            else:  # Pydantic models, etc.
                try:
                    part += f"Data (Object):\n{str(item.data)}"
                except Exception:
                    part += "Data: [Could not serialize data for prompt]"

            formatted_parts.append(part)

        return item_separator.join(formatted_parts)

    # Placeholder for future methods
    def store_context_item(self, item: ContextItem, storage_backend: Any):
        self._logger.warning("Context storage not yet implemented.")
        pass

    def retrieve_context_items(
        self, query: Any, storage_backend: Any
    ) -> List[ContextItem]:
        self._logger.warning("Context retrieval not yet implemented.")
        return []

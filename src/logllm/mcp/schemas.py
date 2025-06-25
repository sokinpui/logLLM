# src/logllm/mcp/schemas.py
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ContextItemType(str, Enum):
    """Enumeration of possible context item types for better type safety."""

    USER_QUERY = "user_query"
    SYSTEM_MESSAGE = "system_message"
    LOG_DATA_RAW = "log_data_raw"
    LOG_DATA_PARSED = "log_data_parsed"
    LOG_SUMMARY = "log_summary"
    ERROR_PATTERN = "error_pattern"
    GROK_PATTERN_SUGGESTION = "grok_pattern_suggestion"
    AGENT_STATE = "agent_state"
    TOOL_RESULT = "tool_result"
    EXTERNAL_KNOWLEDGE = "external_knowledge"  # For RAG outputs
    METRIC_DATA = "metric_data"
    TRACE_DATA = "trace_data"
    USER_FEEDBACK = "user_feedback"
    GENERIC_TEXT = "generic_text"
    GENERIC_STRUCTURED = "generic_structured"
    # Add more specific types as needed


class ContextMetadata(BaseModel):
    """Metadata associated with a context item."""

    source_component: Optional[str] = Field(
        None,
        description="The component that generated this context (e.g., 'ErrorSummarizerAgent', 'UserAPIInput').",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Descriptive tags for categorization and filtering.",
    )
    relevance_score: Optional[float] = Field(
        None,
        description="A score indicating the relevance of this item to the current task.",
    )
    related_item_ids: List[str] = Field(
        default_factory=list,
        description="IDs of other ContextItems this item is related to.",
    )
    # Add other relevant metadata fields like confidence, priority, etc.


class ContextItem(BaseModel):
    """A single piece of contextual information."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this context item.",
    )
    type: Union[ContextItemType, str] = Field(
        ...,
        description="The type of context (e.g., 'log_summary', 'user_query'). Allows custom string types too.",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of when this context item was created or last updated.",
    )
    data: Any = Field(
        ...,
        description="The actual contextual data. Can be a string, dict, or a Pydantic model instance.",
    )
    metadata: ContextMetadata = Field(
        default_factory=ContextMetadata,
        description="Additional metadata about this context item.",
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if isinstance(v, ContextItemType):
            return v.value
        return v


class ContextPayload(BaseModel):
    """A collection of ContextItems, representing the overall context for an operation."""

    items: List[ContextItem] = Field(
        default_factory=list, description="A list of context items."
    )
    # Global metadata for the payload, if needed
    payload_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Overall metadata for this context payload."
    )


# --- Tool Related Schemas ---


class MCPToolParameterSchema(BaseModel):
    """Simplified schema definition for a tool's parameter, similar to JSON Schema properties."""

    type: str = Field(
        ...,
        description="Parameter type (e.g., 'string', 'integer', 'boolean', 'array', 'object').",
    )
    description: Optional[str] = Field(
        None, description="Description of the parameter."
    )
    required: bool = Field(False, description="Whether this parameter is required.")
    enum: Optional[List[Any]] = Field(
        None, description="Possible values for an enum type."
    )
    items: Optional[Dict[str, Any]] = Field(
        None, description="Schema for array items (if type is 'array')."
    )  # Simplified for now
    properties: Optional[Dict[str, Any]] = Field(
        None, description="Schema for object properties (if type is 'object')."
    )  # Simplified


class MCPToolDefinition(BaseModel):
    """Definition of a tool that can be invoked."""

    name: str = Field(
        ...,
        description="The unique name of the tool (e.g., 'fetch_logs_from_elasticsearch').",
    )
    description: str = Field(
        ...,
        description="A clear description of what the tool does, its purpose, and when to use it.",
    )
    parameters: Optional[Dict[str, MCPToolParameterSchema]] = Field(
        None,
        description="A dictionary defining the parameters the tool accepts, keyed by parameter name.",
    )
    # Potentially add:
    # returns: Optional[MCPToolParameterSchema] = Field(None, description="Schema of the data returned by the tool.")


class MCPToolCall(BaseModel):
    """Represents a request from an LLM (or other component) to invoke a specific tool."""

    id: str = Field(
        default_factory=lambda: f"call_{uuid.uuid4()}",
        description="Unique ID for this tool call instance.",
    )
    tool_name: str = Field(
        ...,
        description="The name of the tool to be invoked, matching a ToolDefinition.",
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="The arguments to pass to the tool, as a dictionary.",
    )


class MCPToolResult(BaseModel):
    """Represents the result of a tool invocation."""

    call_id: str = Field(
        ..., description="The ID of the ToolCall this result corresponds to."
    )
    tool_name: str = Field(..., description="The name of the tool that was invoked.")
    output: Any = Field(
        ...,
        description="The data returned by the tool. Can be any valid JSON-serializable type or a Pydantic model instance.",
    )
    is_error: bool = Field(
        False, description="True if the tool invocation resulted in an error."
    )
    error_message: Optional[str] = Field(
        None, description="Error message if is_error is True."
    )

    # Convenience method to create a ContextItem from a ToolResult
    def to_context_item(self) -> ContextItem:
        return ContextItem(
            type=ContextItemType.TOOL_RESULT,
            data=self.model_dump(),  # Store the whole ToolResult object as data
            metadata=ContextMetadata(
                source_component=f"ToolExecutor:{self.tool_name}",
                tags=["tool_execution", "success" if not self.is_error else "error"],
            ),
        )

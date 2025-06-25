# LLM Model Utility (`llm_model.py`)

## File: `src/logllm/utils/llm_model.py`

### Overview

Defines base classes and specific implementations for interacting with Large Language Models (LLMs). This module is designed to be extensible and integrates with the project's **Modern Context Protocol (MCP)** for advanced interactions like structured output and tool use.

### Class: `LLMModel(ABC)`

- **Purpose**: Abstract base class providing a common interface for various LLM implementations.
- **Key Attributes**: `model`, `context_size`, `rpm_limit`, `min_request_interval`, `_last_api_call_time`.
- **Key Methods**:
  - **`__init__(self)`**: Initializes logger and rate limiting defaults.
  - **`_wait_for_rate_limit(self, model_rpm: Optional[int] = None)`**: Pauses execution if the time since the last API call is less than the calculated `min_request_interval`.
  - **`_update_last_call_time(self)`**: Updates the timestamp of the last API call.
  - **`generate(self, prompt_content: Union[str, ContextPayload], output_schema: Optional[Type[BaseModel]] = None, tools: Optional[List[MCPToolDefinition]] = None) -> Union[str, BaseModel, MCPToolCall, None]`**:
    - Abstract method for generating a response from the LLM. _Must be implemented by subclasses._
    - **Parameters**:
      - `prompt_content`: The primary input. Can be a simple `str` or a rich `ContextPayload` from the MCP.
      - `output_schema`: An optional Pydantic `BaseModel` to instruct the LLM to generate a structured JSON output matching this schema.
      - `tools`: An optional list of `MCPToolDefinition`s representing functions the LLM is allowed to call.
    - **Returns**: The response can be:
      - A `str` for a standard text response.
      - A Pydantic `BaseModel` instance if `output_schema` was successfully fulfilled.
      - An `MCPToolCall` instance if the LLM decides to use one of the provided `tools`.
      - `None` if the call fails or is blocked.
  - **`token_count(self, text_content: str | None) -> int`**: Abstract method for counting tokens. _Must be implemented by subclasses._
  - **`generate_embeddings(self, contents: Union[str, List[str]], ..., output_dimensionality: Optional[int] = None) -> List[List[float]]`**: Abstract method for generating embeddings. _Must be implemented by subclasses._

### Class: `GeminiModel(LLMModel)`

- **Purpose**: Implements interaction with Google's Gemini models using the direct `google-generativeai` SDK.
- **Key Methods**:

  - **`__init__(self, model_name: str | None = None)`**:
    - Initializes the connection to the Gemini API using `GENAI_API_KEY`.
    - Sets model-specific rate limits (`rpm_limit`) and context size.
  - **`token_count(self, text_content: str | None) -> int`**:
    - Implements token counting, preferring local `vertexai` tokenization for speed and falling back to an API call.
  - **`generate(self, prompt_content: Union[str, ContextPayload], ...)`**:
    - Implements the core generation logic.
    - **Handles `prompt_content`**: If it's a `ContextPayload`, it uses `ContextManager` to format it into a string for the prompt. Otherwise, it uses the provided string directly.
    - **Handles `output_schema`**: Converts the Pydantic model into a Gemini-compatible `Tool` and instructs the model to use it for structured output. If successful, it validates and returns the Pydantic object.
    - **Handles `tools`**: Converts the list of `MCPToolDefinition`s into Gemini-compatible `Tool`s. If the LLM's response is a function call corresponding to one of these tools, it returns an `MCPToolCall` object, which the calling code is responsible for executing.
    - Manages the logic to parse the LLM's response and return the correct type (`str`, `BaseModel`, or `MCPToolCall`).
  - **`generate_embeddings(self, contents: Union[str, List[str]], ...)`**:
    - Generates embeddings for text.
    - **Handles long texts by chunking**: If a text item exceeds the embedding model's token limit, it is automatically chunked, and the resulting embeddings are averaged to produce a single representative vector.
    - Correctly handles empty inputs and reconstructs the output list to align with the input list.
  - **`_mcp_tool_definitions_to_gemini_tools(...)`**: Internal helper to convert MCP tool definitions to the provider-specific format.
  - **`_average_embeddings(...)` & `_split_text_into_chunks(...)`**: Internal helpers for the embedding process.

- **Utility Function**: **`pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool`**:

  - Converts a Pydantic model into a `google.ai.generativelanguage.Tool` object compatible with the Gemini API's function calling feature. Handles type mapping and schema properties.

- **Constants**:
  - `MODEL_RPM_LIMITS`: Dictionary mapping Gemini model names to their requests-per-minute limits.
  - `EMBEDDING_MODEL_TOKEN_LIMITS`: Dictionary mapping embedding model names to their input token limits.

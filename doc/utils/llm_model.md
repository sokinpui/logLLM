# LLM Models Module (`llm_models/`)

### Overview

The `logllm.utils.llm_models` module provides a structured and extensible framework for interacting with various Large Language Models (LLMs). It contains specific implementations for different LLM providers like Google Gemini and local Ollama instances.

The module is intentionally designed to be **pluggable**. The primary reason for its architecture is to make it easy for developers to add support for new LLM providers. This is achieved by using an abstract base class, `LLMModel` (defined in `llm_abc.py`), which acts as a "contract" that all model implementations must follow.

To integrate a new LLM provider, a developer simply needs to:

1.  Create a new file (e.g., `anthropic_model.py`) within the `llm_models` directory.
2.  Define a new class that inherits from `LLMModel`.
3.  Implement the required abstract methods: `generate()`, `token_count()`, and `generate_embeddings()`. Within these methods, the developer will write the specific logic to call the new provider's API and translate its responses into the common formats defined by the base class.

This design ensures that any part of the application can use any supported LLM interchangeably. It also guarantees that advanced features like structured output (`output_schema`) and tool use (`tools`), which are part of the **Modern Context Protocol (MCP)**, are handled consistently across all model implementations.

### Module Structure

This module is organized as a Python package with the following structure:

- **`src/logllm/utils/llm_models/`**: The main package directory.
  - **`__init__.py`**: Exposes the primary classes (`LLMModel`, `GeminiModel`, `OllamaModel`) for convenient importing.
  - **`llm_abc.py`**: Contains the `LLMModel` abstract base class, which defines the standard interface for all model implementations.
  - **`gemini_model.py`**: The implementation for interacting with Google's Gemini models.
  - **`ollama_model.py`**: The implementation for interacting with models served by an Ollama instance.

---

## Abstract Base Class (`llm_abc.py`)

### Class: `LLMModel(ABC)`

- **File**: `src/logllm/utils/llm_models/llm_abc.py`
- **Purpose**: This abstract base class defines the "contract" that all LLM model implementations must follow. It ensures that any model from this module can be used interchangeably, as they all share the same core methods and properties.
- **Key Attributes**:
  - `model`: The underlying provider-specific model object.
  - `context_size`: The token limit for the model's context window.
  - `model_name`: The name of the specific LLM being used (e.g., "gemini-1.5-pro").
- **Abstract Methods (to be implemented by subclasses)**:
  - **`generate(self, prompt_content: Union[str, ContextPayload], output_schema: Optional[Type[BaseModel]] = None, tools: Optional[List[MCPToolDefinition]] = None) -> Union[str, BaseModel, MCPToolCall, None]`**:
    - The primary method for generating a response from the LLM.
    - **Usage**:
      - Pass a `str` to `prompt_content` for a simple query.
      - Pass a `ContextPayload` object for a more complex, structured prompt.
      - Provide a Pydantic `BaseModel` to the `output_schema` parameter to force the LLM to return a structured JSON object that matches the schema.
      - Provide a list of `MCPToolDefinition`s to the `tools` parameter to allow the LLM to call functions.
    - **Returns**: The response will be a `str` for plain text, a Pydantic `BaseModel` instance for structured output, an `MCPToolCall` instance if a tool is used, or `None` on failure.
  - **`token_count(self, text_content: str | None) -> int`**:
    - Calculates the number of tokens in a given string according to the model's specific tokenizer.
  - **`generate_embeddings(self, contents: Union[str, List[str]], ...) -> List[List[float]]`**:
    - Generates vector embeddings for a given string or a list of strings.

---

## Model Implementations

### Class: `GeminiModel(LLMModel)`

- **File**: `src/logllm/utils/llm_models/gemini_model.py`
- **Purpose**: Use this class to interact with Google's Gemini models via the `google-generativeai` SDK. It handles API authentication, rate limiting, and mapping MCP features to the Gemini API.
- **How to Use**:
  - **Initialization**: `model = GeminiModel(model_name="gemini-1.5-pro-latest")`. Before use, ensure the `GENAI_API_KEY` environment variable is set.
  - **Rate Limiting**: The class automatically respects the requests-per-minute (RPM) limits for the specified Gemini model, pausing execution if necessary.
  - **Generation (`generate`)**:
    - Supports all features of the base class: simple prompts, `ContextPayload`, structured output via `output_schema`, and tool use via `tools`.
    - It transparently converts Pydantic schemas and `MCPToolDefinition`s into the format required by the Gemini API.
  - **Token Counting (`token_count`)**:
    - Provides accurate token counts. It attempts to use a fast, local tokenizer from the `vertexai` library (if installed) and falls back to a slower API call if needed.
  - **Embeddings (`generate_embeddings`)**:
    - Handles texts that exceed the token limit of the embedding model (e.g., `text-embedding-004`) by automatically splitting the text into chunks, generating embeddings for each, and averaging them into a single representative vector.
- **Utility Function**:
  - `pydantic_to_google_tool()`: A helper function within the file that converts a Pydantic model into a `Tool` object compatible with the Gemini API. This is used internally by the `generate` method.

### Class: `OllamaModel(LLMModel)`

- **File**: `src/logllm/utils/llm_models/ollama_model.py`
- **Purpose**: Use this class to interact with any LLM served by a local or remote Ollama instance. This is ideal for development, testing, or using open-source models.
- **How to Use**:
  - **Initialization**: `model = OllamaModel(model_name="llama3", ollama_host="http://localhost:11434")`. Ensure the Ollama application is running and the specified model is pulled (`ollama pull llama3`).
  - **Generation (`generate`)**:
    - **Structured Output**: To get a JSON response, pass a Pydantic `BaseModel` to the `output_schema` parameter. The class will instruct Ollama to use JSON mode and then validate the response against your schema.
    - **Tool Use**: Pass a list of `MCPToolDefinition`s to the `tools` parameter. The class converts them to the format Ollama expects and will return an `MCPToolCall` if the model decides to use a tool.
  - **Token Counting (`token_count`)**:
    - Provides a basic estimation by counting words. This is a fallback because the `ollama` library does not expose a model-specific tokenizer. For higher accuracy, consider using a separate tokenizer library like `tiktoken`.
  - **Embeddings (`generate_embeddings`)**:
    - Generates embeddings using the specified `embedding_model_name`. It calls the Ollama server's embedding endpoint for each string provided.

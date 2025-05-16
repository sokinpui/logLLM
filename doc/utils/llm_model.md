# LLM Model Utility (`llm_model.py`)

## File: `src/logllm/utils/llm_model.py`

### Overview

Defines base classes and specific implementations for interacting with Large Language Models (LLMs). Includes handling for API calls, token counting, and structured output generation.

### Class: `LLMModel(ABC)`

- **Purpose**: Abstract base class providing a common interface for various LLM implementations (e.g., Gemini).
- **Key Attributes**: `model`, `embedding`, `context_size`, `rpm_limit`, `min_request_interval`, `_last_api_call_time`.
- **Key Methods**:
  - **`__init__(self)`**: Initializes logger, rate limiting defaults.
  - **`_wait_for_rate_limit(self)`**: Pauses execution if the time since the last API call is less than the calculated `min_request_interval`.
  - **`_update_last_call_time(self)`**: Updates the timestamp of the last API call.
  - **`generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None)`**: Abstract method for generating text or structured output. _Must be implemented by subclasses._
  - **`token_count(self, prompt: str | None) -> int`**: Abstract method for counting tokens. _Must be implemented by subclasses._

### Class: `GeminiModel(LLMModel)`

- **Purpose**: Implements interaction with Google's Gemini models using the direct `google-generativeai` SDK.
- **Key Methods**:

  - **`__init__(self, model_name: str | None = None)`**:
    - Initializes the connection to the Gemini API using `GENAI_API_KEY` environment variable.
    - Sets the `model_name` (defaults to `cfg.GEMINI_LLM_MODEL`).
    - Configures rate limiting (`rpm_limit`, `min_request_interval`) based on the specific Gemini model using `MODEL_RPM_LIMITS`.
    - Initializes `genai.GenerativeModel` for generation and `GoogleGenerativeAIEmbeddings` (from Langchain) for embeddings.
  - **`token_count(self, prompt: str | None) -> int`**: Implements token counting using `self.model.count_tokens()`. Includes basic fallback estimate.
  - **`generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None)`**:
    - Implements generation using `self.model.generate_content()`.
    - Applies rate limiting (`_wait_for_rate_limit`).
    - If `schema` (Pydantic model) is provided:
      - Converts the schema to a Google API `Tool` using `pydantic_to_google_tool`.
      - Instructs the model to use the tool (`function_calling_config`).
      - Parses the model's function call response (converting `fc.args` to a `dict`), validates against the schema, and returns the Pydantic object.
    - If no schema or function call fails/is absent, returns the text content (`response.text`).
    - Includes error handling for API errors, validation errors, and safety blocking.

- **Utility Function**: **`pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool`**:
  - Converts a Pydantic model into a `google.ai.generativelanguage.Tool` object compatible with the Gemini API's function calling feature. Handles type mapping and schema properties.

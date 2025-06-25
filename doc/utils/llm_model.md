# LLM Model Utility (`llm_model.py`)

## File: `src/logllm/utils/llm_model.py`

### Overview

Defines base classes and specific implementations for interacting with Large Language Models (LLMs). Includes handling for API calls, token counting, structured output generation, and text embeddings.

### Class: `LLMModel(ABC)`

- **Purpose**: Abstract base class providing a common interface for various LLM implementations (e.g., Gemini).
- **Key Attributes**: `model`, `context_size`, `rpm_limit`, `min_request_interval`, `_last_api_call_time`.
- **Key Methods**:
  - **`__init__(self)`**: Initializes logger, rate limiting defaults.
  - **`_wait_for_rate_limit(self, model_rpm: Optional[int] = None)`**: Pauses execution if the time since the last API call is less than the calculated `min_request_interval` for the given `model_rpm` or the default.
  - **`_update_last_call_time(self)`**: Updates the timestamp of the last API call.
  - **`generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None)`**: Abstract method for generating text or structured output. _Must be implemented by subclasses._
  - **`token_count(self, prompt: str | None) -> int`**: Abstract method for counting tokens. _Must be implemented by subclasses._
  - **`generate_embeddings(self, contents: Union[str, List[str]], ..., output_dimensionality: Optional[int] = None) -> List[List[float]]`**: Abstract method for generating embeddings. _Must be implemented by subclasses._

### Class: `GeminiModel(LLMModel)`

- **Purpose**: Implements interaction with Google's Gemini models using the direct `google-generativeai` SDK.
- **Key Methods**:

  - **`__init__(self, model_name: str | None = None)`**:
    - Initializes the connection to the Gemini API using `GENAI_API_KEY` environment variable.
    - Sets the `model_name` (defaults to `cfg.GEMINI_LLM_MODEL`).
    - Configures rate limiting (`rpm_limit`, `min_request_interval`) based on the specific Gemini model using `MODEL_RPM_LIMITS`.
    - Initializes `genai.GenerativeModel` for generation.
    - Sets `default_embedding_model` (e.g., `"models/text-embedding-004"`).
  - **`token_count(self, prompt: str | None) -> int`**:
    - Implements token counting.
    - Prioritizes `vertexai.preview.tokenization` if available for more accurate local counting, especially for chunking estimations.
    - Falls back to `self.model.count_tokens()` (API call).
    - Basic fallback to `len(prompt.split())` if API call fails.
  - **`generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None)`**:
    - Implements generation using `self.model.generate_content()`.
    - Applies rate limiting (`_wait_for_rate_limit`).
    - If `schema` (Pydantic model) is provided:
      - Converts the schema to a Google API `Tool` using `pydantic_to_google_tool`.
      - Instructs the model to use the tool (`function_calling_config`).
      - Parses the model's function call response (converting `fc.args` to a `dict`), validates against the schema, and returns the Pydantic object.
    - If no schema or function call fails/is absent, returns the text content (`response.text`).
    - Includes error handling for API errors, validation errors, and safety blocking.
  - **`generate_embeddings(self, contents: Union[str, List[str]], embedding_model_name: Optional[str] = None, task_type: Optional[str] = None, title: Optional[str] = None, output_dimensionality: Optional[int] = None) -> List[List[float]]`**:
    - Generates embeddings for a single string or a list of strings.
    - Uses `embedding_model_name` if provided, else `self.default_embedding_model`.
    - Applies rate limiting specific to the chosen embedding model's RPM.
    - **Handles long texts by chunking**: If a text item exceeds the embedding model's token limit (defined in `EMBEDDING_MODEL_TOKEN_LIMITS`), it's split into smaller chunks using `_split_text_into_chunks`. Embeddings for these chunks are then averaged using `_average_embeddings` to produce a single embedding for the original long text.
    - Returns a list of embedding vectors. Each vector corresponds to an input string in `contents`. If an input string was empty or resulted in an error, its corresponding entry in the output list will be an empty list `[]`.
  - **`_average_embeddings(self, embeddings: List[List[float]]) -> List[float]`**:
    - Internal helper to calculate the element-wise average of a list of embedding vectors. Used when a single text is chunked.
  - **`_split_text_into_chunks(self, text: str, chunk_token_limit: int, chunk_word_overlap: int = 50) -> List[str]`**:
    - Internal helper to split a long text into manageable chunks based on estimated token count, with a specified word overlap.

- **Utility Function**: **`pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool`**:

  - Converts a Pydantic model into a `google.ai.generativelanguage.Tool` object compatible with the Gemini API's function calling feature. Handles type mapping and schema properties.

- **Constants**:
  - `MODEL_RPM_LIMITS`: Dictionary mapping Gemini model names to their requests-per-minute limits.
  - `EMBEDDING_MODEL_TOKEN_LIMITS`: Dictionary mapping embedding model names to their input token limits.

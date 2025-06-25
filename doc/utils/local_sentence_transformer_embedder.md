# Local Sentence Transformer Embedder Utility (`local_embedder.py`)

## File: `src/logllm/utils/local_embedder.py`

### Overview

The `LocalSentenceTransformerEmbedder` class provides a wrapper for using Sentence Transformer models locally to generate text embeddings. This is an alternative to API-based embedding models, useful for offline scenarios, cost savings, or when specific local models are preferred.

### Class: `LocalSentenceTransformerEmbedder`

- **Purpose**: Loads a specified Sentence Transformer model (e.g., from Hugging Face Hub or a local path) and provides a method to generate embeddings for text inputs. It includes a class-level cache to avoid reloading the same model multiple times.
- **Key Attributes**:

  - `model_name` (str): The name or path of the Sentence Transformer model.
  - `device` (str): The device to run the model on (e.g., "cuda", "mps", "cpu"), automatically detected if not specified.
  - `model` (SentenceTransformer): The loaded Sentence Transformer model instance.
  - `max_seq_length` (int): The maximum sequence length supported by the loaded model.
  - `_model_cache` (Dict[str, SentenceTransformer]): Class-level static cache for loaded models.

- **Key Methods**:

  - **`__init__(self, model_name_or_path: str = "sentence-transformers/all-MiniLM-L6-v2", device: Optional[str] = None, logger: Optional[Logger] = None)`**:

    - **Description**: Initializes the embedder.
      - Sets the `model_name_or_path`.
      - Determines the `device` (CUDA, MPS, or CPU).
      - Loads the Sentence Transformer model using `SentenceTransformer(model_name_or_path, device=self.device)`.
      - Caches the loaded model in `_model_cache` to prevent redundant loading if multiple instances request the same model.
    - **Parameters**:
      - `model_name_or_path` (str): The identifier for the Sentence Transformer model (e.g., "sentence-transformers/all-MiniLM-L6-v2", "/path/to/local/model").
      - `device` (Optional[str]): Explicitly specify the device ("cuda", "mps", "cpu"). Auto-detected if `None`.
      - `logger` (Optional[Logger]): An optional logger instance.

  - **`generate_embeddings(self, contents: Union[str, List[str]], batch_size: int = 32, show_progress_bar: bool = False, normalize_embeddings: bool = True) -> List[List[float]]`**:

    - **Description**: Generates embeddings for the given text(s).
    - **Parameters**:
      - `contents` (Union[str, List[str]]): A single string or a list of strings to embed.
      - `batch_size` (int): Batch size for encoding when `contents` is a list. Sentence Transformer's `encode` method handles this efficiently.
      - `show_progress_bar` (bool): Whether to display a progress bar during encoding (useful for large lists).
      - `normalize_embeddings` (bool): If `True`, normalizes the embeddings to unit length, which is often beneficial for cosine similarity.
    - **Returns**: `List[List[float]]`. A list of embedding vectors. If the input `contents` was a single string, the output is a list containing a single embedding vector. If an input string is empty or only whitespace, its corresponding output embedding will be an empty list `[]`.
    - **Note**: The underlying Sentence Transformer `encode` method handles truncation for inputs longer than the model's `max_seq_length`.

  - **`token_count(self, text: str) -> int`**:
    - **Description**: Estimates the token count of a given text using the model's specific tokenizer.
    - **Parameters**:
      - `text` (str): The input string.
    - **Returns**: (int): The number of tokens as determined by the model's tokenizer. Falls back to word count if tokenization fails.

### Usage Example

```python
from logllm.utils.local_embedder import LocalSentenceTransformerEmbedder
from logllm.utils.logger import Logger

logger = Logger()

# Initialize with default model
embedder = LocalSentenceTransformerEmbedder(logger=logger)

texts = ["This is the first document.", "Another document for embedding."]
embeddings = embedder.generate_embeddings(texts)

for text, embedding in zip(texts, embeddings):
    print(f"Text: {text}")
    print(f"Embedding (first 5 dims): {embedding[:5]}")
    print(f"Token count: {embedder.token_count(text)}")

# Initialize with a different model
# embedder_custom = LocalSentenceTransformerEmbedder(model_name_or_path="paraphrase-MiniLM-L3-v2", logger=logger)
# custom_embeddings = embedder_custom.generate_embeddings("Test sentence with custom model.")
```

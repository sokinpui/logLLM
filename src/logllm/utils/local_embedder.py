# src/logllm/utils/local_embedder.py
from typing import List, Optional, Union, Dict, Any
import torch
from sentence_transformers import SentenceTransformer
from .logger import Logger


class LocalSentenceTransformerEmbedder:
    """
    A wrapper for using Sentence Transformer models locally for embeddings.
    """

    _model_cache: Dict[str, SentenceTransformer] = {}  # Class-level cache for models

    def __init__(
        self,
        model_name_or_path: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        self.logger = logger or Logger()
        self.model_name = model_name_or_path

        if device:
            self.device = device
        elif torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():  # For Apple Silicon
            self.device = "mps"
        else:
            self.device = "cpu"

        self.logger.info(
            f"LocalSentenceTransformerEmbedder: Using device '{self.device}' for model '{self.model_name}'."
        )

        if self.model_name not in LocalSentenceTransformerEmbedder._model_cache:
            try:
                self.logger.info(
                    f"Loading local sentence transformer model: {self.model_name}..."
                )
                # Load the model and move it to the specified device
                model = SentenceTransformer(self.model_name, device=self.device)
                LocalSentenceTransformerEmbedder._model_cache[self.model_name] = model
                self.logger.info(
                    f"Successfully loaded model '{self.model_name}' to cache."
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to load sentence transformer model '{self.model_name}': {e}",
                    exc_info=True,
                )
                raise

        self.model = LocalSentenceTransformerEmbedder._model_cache[self.model_name]

        # Get max sequence length (useful for very long individual log lines, though rare)
        self.max_seq_length = self.model.get_max_seq_length()
        self.logger.debug(
            f"Model '{self.model_name}' max sequence length: {self.max_seq_length} tokens."
        )

    def generate_embeddings(
        self,
        contents: Union[str, List[str]],
        batch_size: int = 32,  # SentenceTransformer's encode handles batching well
        show_progress_bar: bool = False,  # Progress bar for long lists
        normalize_embeddings: bool = True,  # Often good for cosine similarity
    ) -> List[List[float]]:
        """
        Generates embeddings for the given text contents.

        Args:
            contents: A single string or a list of strings to embed.
            batch_size: Batch size for encoding (if contents is a list).
            show_progress_bar: Whether to show a progress bar during encoding.
            normalize_embeddings: Whether to normalize embeddings to unit length.

        Returns:
            A list of embedding vectors (List[List[float]]).
            If input was a single string, output is List[List[float]] with one item.
        """
        if not contents:
            return []

        is_single_string = isinstance(contents, str)
        if is_single_string:
            texts_to_embed = [contents]
        else:
            texts_to_embed = contents

        # Filter out any None or empty strings from the list to prevent errors with encode
        valid_texts_to_embed = [
            text for text in texts_to_embed if text and text.strip()
        ]
        if not valid_texts_to_embed:
            self.logger.warning("No valid (non-empty) texts provided for embedding.")
            # Return a list of empty lists matching the original input structure if needed for alignment
            return [[] for _ in texts_to_embed]

        self.logger.info(
            f"Generating {len(valid_texts_to_embed)} embeddings locally using '{self.model_name}' (batch size: {batch_size})."
        )
        try:
            # The `encode` method can take a list of sentences.
            # It handles truncation for inputs longer than max_seq_length.
            embeddings = self.model.encode(
                valid_texts_to_embed,
                batch_size=batch_size,
                show_progress_bar=show_progress_bar,
                normalize_embeddings=normalize_embeddings,
                convert_to_tensor=False,  # Get numpy arrays
                device=self.device,
            )
            # Convert numpy.ndarray to List[List[float]]
            embeddings_list = [emb.tolist() for emb in embeddings]  # type: ignore

            # Reconstruct the output to match the original input structure, inserting empty lists for invalid texts
            final_embeddings: List[List[float]] = []
            valid_emb_iter = iter(embeddings_list)
            for text in texts_to_embed:
                if text and text.strip():
                    try:
                        final_embeddings.append(next(valid_emb_iter))
                    except StopIteration:
                        self.logger.error(
                            "Mismatch between number of valid texts and generated embeddings. This should not happen."
                        )
                        final_embeddings.append([])  # Placeholder for error
                else:
                    final_embeddings.append([])

            return final_embeddings

        except Exception as e:
            self.logger.error(
                f"Error generating local embeddings with '{self.model_name}': {e}",
                exc_info=True,
            )
            # Return empty embeddings for all inputs on error
            return [[] for _ in texts_to_embed]

    def token_count(self, text: str) -> int:
        """
        Estimates token count based on the model's tokenizer.
        Note: SentenceTransformer models often have their own specific tokenization.
        """
        if not text or not hasattr(self.model, "tokenizer"):
            return 0
        try:
            # This gives the number of tokens *after* special tokens are added and truncation/padding might occur
            # It's more about what the model sees.
            return len(self.model.tokenizer.encode(text, add_special_tokens=True))
        except Exception as e:
            self.logger.warning(
                f"Could not get token count for model {self.model_name}: {e}. Falling back to word count."
            )
            return len(text.split())

from typing import Any, Callable

from .database import ElasticsearchDatabase


class ESTextChunkManager:
    """
    Manage the chunk of text to analyze.
    Retrieve the chunk from Elasticsearch

    Args:
        id: The id that is used to retrieve the text
        field: field to retrieve the text
        index: index of the document
        db: ElasticsearchDatabase instance
    """

    def __init__(self, id: Any, field: str, index: str, db: ElasticsearchDatabase):
        self.id = id
        self.field = field
        self._index = index
        self._db = db

        self.hits: list = self._get_all_hits()
        self.total_hits: int = len(self.hits)

        self.start = 0

        self.hits_in_current_chunk = 0
        self.current_chunk: str | None = None

    def _build_chunk(
        self,
        initial_size: int,
        start: int,
        hits: list,
        max_len: int,
        len_fn: Callable[[str], int],
    ) -> str:
        """
        Build the chunk of text from the hits

        Args:
            initial_size: initial size of the chunk
            start: start index of the hits
            hits: list of hits return from the Elasticsearch `response["hits"]["hits"]`
            max_len: maximum length of the chunk
            len_fn: function to calculate the length of the text
        """
        chunk = ""
        total_tokens = 0
        start = start
        hits_length = len(hits)
        current_size = initial_size  # Start with the initial size (e.g., 512)
        count = 0

        while total_tokens < max_len and start < hits_length:
            end = start + current_size

            current_hits = hits[start:end]
            if not current_hits:
                break  # No more hits to process

            tmp = "".join(hit["_source"]["content"] for hit in current_hits)
            tmp_tokens = len_fn(tmp)

            if total_tokens + tmp_tokens > max_len:
                if current_size == 1:
                    break  # Smallest size still exceeds; skip remaining
                current_size = max(1, current_size // 2)  # Halve the size
                continue  # Retry with smaller size at the same start position

            # Add the chunk and advance
            count += current_size
            chunk += tmp
            total_tokens += tmp_tokens
            start += current_size

        self.start = start
        self.hits_in_current_chunk = count

        return chunk

    def _get_all_hits(self) -> list:
        """
        Get all the hits from the Elasticsearch
        """
        query = {"query": {"match": {"id": self.id}}, "_source": [self.field]}

        return self._db.scroll_search(index=self._index, query=query)

    def is_end(self) -> bool:
        """
        Check if the end of the hits is reached
        """
        return self.start >= self.total_hits

    def get_next_chunk(self, max_len: int, len_fn: Callable[[str], int]) -> str:
        """
        Get the next chunk of text to analyze,
        the status of the chunk is stored in the class
        Start index is updated after each call

        Args:
            max_tokens: maximum tokens to analyze
            token_count: function to count the tokens in the text

        Returns:
            str: chunk of text
            None: if no more hits to process

        """
        if self.is_end():
            print("No more hits to process")
            return ""

        chunk = self._build_chunk(2**10, self.start, self.hits, max_len, len_fn)

        self.current_chunk = chunk

        return chunk

    def get_current_chunk(self) -> str | None:
        return self.current_chunk


def test_chunk_manager(
    chunk_manager: ESTextChunkManager,
    max_tokens: int,
    token_count: Callable[[str], int],
    model,
):
    """
    Test function to loop through all hits and print the state of each loop.

    Args:
        chunk_manager: An instance of ESTextChunkManager.
        max_tokens: Maximum tokens allowed per chunk.
        token_count: Function to count tokens in a text.
    """
    print("Starting test...")
    while not chunk_manager.is_end():
        # Get the next chunk
        chunk = chunk_manager.get_next_chunk(max_tokens, token_count)

        # If no more chunks, break the loop
        if chunk is None:
            print("No more chunks to process. Test complete.")
            break

        # Print the state of the loop
        print(
            f"Start index: {chunk_manager.start}, hits in this round: {chunk_manager.hits_in_current_chunk}, Chunk token length: {model.token_count(chunk)}"
        )

    print("Test complete. All hits processed.")

from langchain_core import embeddings

from langchain_community.document_loaders import DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .logger import Logger
from .llm_model import LLMModel
from .database import ElasticsearchDatabase
from prompts import rag as pr
from ..config import config as cfg

_CHUNK_SIZE = 512  # chunk size of the documents
_CHUNK_OVERLAP = 20


class RAGManager:
    """
    RAGManager is a class that manages the documents to provide context for the model
    Use Elasticsearch to provide a vector store for the embedded documents
    """

    def __init__(
        self,
        name: str,  # provide a name for this set of documents
        db: ElasticsearchDatabase,
        embeddings,
        model: LLMModel,
        multi_threading: bool = False,
    ):
        self.name = name
        self._db_index = f"{cfg.INDEX_VECTOR_STORE}_{name}"

        self._model = model
        self._embeddings = embeddings

        self._vector_store = db.set_vector_store(
            embeddings=embeddings, index=self._db_index
        )

        self._multi_threading = multi_threading
        self._logger = Logger()

    def retrieve(self, prompt: str) -> str:
        """
        get retrieved context from the vector store
        """
        retrieved_docs = self._vector_store.similarity_search(query=prompt, k=5)
        self._logger.info(
            f"RAG: Retrieved {len(retrieved_docs)} documents, from {self._db_index}"
        )

        docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)

        contextual_prompt = pr.prompt(question=prompt, context=docs_content)

        return contextual_prompt

    def _load_from_directory(self, directory: str, file_extension: str = "md"):
        loader = DirectoryLoader(
            path=directory,
            glob=f"**/*.{file_extension}",
            load_hidden=False,
            recursive=True,
            use_multithreading=self._multi_threading,
        )

        try:
            self._logger.info(f"RAG: Loading documents from {directory}.....")
            rag_docs = loader.load()
            self._logger.info(f"RAG: Loaded {len(rag_docs)} documents from {directory}")
        except Exception as e:
            self._logger.error(f"Error loading documents from {directory}: {e}")
            exit(1)

        # set up text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_CHUNK_SIZE,
            chunk_overlap=_CHUNK_OVERLAP,
            length_function=self._model.token_count,
        )
        # splits
        splits = text_splitter.split_documents(rag_docs)

        ids = [
            f"{split.metadata['source']}_chunk_{i}" for i, split in enumerate(splits)
        ]

        # index and store to vector store
        try:
            _ = self._vector_store.add_documents(documents=splits, ids=ids)
            self._logger.info(f"RAG: Added {len(rag_docs)} documents to vector store")
            self._is_loaded = True
        except Exception as e:
            self._logger.error(f"Error adding documents to vector store: {e}")
            exit(1)

    def update_rag_from_directory(
        self, directory: str, db: ElasticsearchDatabase, file_extension: str = "md"
    ):
        """
        should provided a directory of markdown files
        """

        if db.instance.indices.exists(index=self._db_index):
            db.instance.indices.delete(index=self._db_index)
            self._logger.info(f"RAG: earse old documents from {self._db_index}")

        self._load_from_directory(directory, file_extension)


def main():
    pass


if __name__ == "__main__":
    main()

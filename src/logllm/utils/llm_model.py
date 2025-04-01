import tiktoken
import os
from vertexai.preview import tokenization
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from langchain_community.llms import LlamaCpp
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
from langchain_ollama import OllamaEmbeddings
from llama_cpp import Llama
from contextlib import redirect_stdout, redirect_stderr

from .logger import Logger
from ..config import config as cfg


class LLMModel:
    """
    provide common interface for Gemini model, but user can still access the model-specific methods via `self.model`
    """
    def __init__(self):
        self._logger = Logger()
        self.model = None
        self.embedding = None
        self.context_size = 0

    def generate(self, prompt, schema=None):
        if schema:
            model = self.model.with_structured_output(schema)
            structured_output = model.invoke(prompt)
            return structured_output

        response = self.model.invoke(prompt)
        content = response.content

        return content

    def token_count(self, prompt: str) -> int:
        tokenizer = tiktoken.get_encoding("cl100k_base")

        tokens = tokenizer.encode(prompt)
        token_count = len(tokens)
        return token_count

class GeminiModel(LLMModel):
    # Gemini-specific implementation
    """
    by default, asusme using gemini flash 2.0
    """
    def __init__(self):
        super().__init__()

        self.context_size = 100000

        model = cfg.GEMINI_LLM_MODEL
        api_key = os.environ['GENAI_API_KEY']
        if api_key is None:
            self._logger.error("Please define GENAI_API_KEY in the environment variable")
            raise ValueError("Please define GENAI_API_KEY in the environment variable")
        os.environ["GOOGLE_API_KEY"] = api_key

        try:
            self.model = ChatGoogleGenerativeAI(model=model, temperature=0)

            # set the embedding model
            self.embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

            self._logger.info(f"Gemini model {model} is using, Gemini model initialized")
        except Exception as e:
            self._logger.error(f"Error in initializing Gemini model: {e}")

    def token_count(self, prompt: str | None) -> int:

        if prompt is None:
            return 0

        tokenizer = tokenization.get_tokenizer_for_model("gemini-1.5-flash")

        result = tokenizer.count_tokens(prompt)
        return result.total_tokens

    def generate(self, prompt, schema=None):
        result = super().generate(prompt, schema)

        import time
        time.sleep(5)

        return result



class QwenModel(LLMModel):
    def __init__(self):
        super().__init__()
        path = "./models/qwen/qwen2.5-7b-instruct-1m-q4_k_m.gguf"
        self.n_gpu_layers = -1
        self.n_batch = 512

        self.context_size = 128000


        with open(os.devnull, 'w') as f, redirect_stdout(f), redirect_stderr(f):
            self.model = LlamaCpp(
                    model_path=path,
                    n_gpu_layers=self.n_gpu_layers,
                    n_batch=self.n_batch,
                    callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
                    verbose=False
                    )

            # set the embedding model
            self._llm_raw = Llama(model_path=path, n_ctx=self.context_size, verbose=False)
            self.embedding = OllamaEmbeddings(model="qwen2.5")

    def token_count(self, text: str | None) -> int:
        if text is None:
            return 0

        tokens = self._llm_raw.tokenize(text.encode("utf-8"))
        return len(tokens)

    def generate(self, prompt, schema=None):
        if schema:
            model = self.model.with_structured_output(schema)
            structured_output = model.invoke(prompt)
            return structured_output

        return self.model.invoke(prompt)

def main():
    # test the Gemini model
    model = GeminiModel()
    prompt = "What is the capital of France?"
    print(f"token count: {model.token_count(prompt)}")
    print(model.model.invoke(prompt))

    prompt2 = "What is the capital of Germany?"
    print(model.generate(prompt2))

if __name__ == "__main__":
    main()

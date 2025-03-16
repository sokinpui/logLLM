from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from vertexai.preview import tokenization
import tiktoken
from pydantic import BaseModel, Field
import os

import config as cfg
from logger import Logger


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

        tokenizer = tokenization.get_tokenizer_for_model(cfg.GEMINI_LLM_MODEL.replace("2.0", "1.5"))

        result = tokenizer.count_tokens(prompt)
        return result.total_tokens




def main():
    # test the Gemini model
    model = GeminiModel()
    prompt = "What is the capital of France?"
    print(f"token count: {model.token_count(prompt)}")

if __name__ == "__main__":
    main()

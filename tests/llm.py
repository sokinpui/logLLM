import os
from logllm.config import config as cfg
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List

model_name = cfg.GEMINI_LLM_MODEL
api_key = os.environ['GENAI_API_KEY']
os.environ["GOOGLE_API_KEY"] = api_key

model = ChatGoogleGenerativeAI(model=model_name, temperature=0, verbose=False)

prompt = "give me a list of 10 integer"

class schema(BaseModel):
    list_of_int: list[str] = Field(description="list of integer generated")

response = model.invoke(prompt)

smodel = model.with_structured_output(schema)
structured_output = smodel.invoke(prompt)

print(response.content)

print(structured_output)

from logllm.utils.llm_model import GeminiModel

model = GeminiModel()

print(model.generate(prompt, schema))

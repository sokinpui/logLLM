from llm_model import GeminiModel
from database import ElasticsearchDatabase
from collector import Collector
from rag_manager import RAGManager
from data_struct import Event
from .pre_process_agent import PreProcessAgent
from .linear_analyze_agent import LinearAnalyzeAgent

import json

model = GeminiModel()
es_db = ElasticsearchDatabase()
collector = Collector(dir="../log")

# create rag manager
embeddings = model.embedding
sys_info = RAGManager(name="systme_los_info_overview", db=es_db, embeddings=embeddings, model=model)

# sys_info.update_rag_from_directory("../rag/docs/", es_db)

e1 = Event(description="Is IP address 185.165.29.69 keep attempting to login as Invalid user via ssh")

node1 = PreProcessAgent(model=model, rag=sys_info, db=es_db)

state = {
    "working_event": e1,
    "files": collector.collected_files,
}

# result1 = node1.run(state)
# result1["files"] = None
# result1["working_event"] = None
# with open("result1.json", "w") as f:
    # json.dump(result1, f, indent=4)

node2 = LinearAnalyzeAgent(model=model, db=es_db)

with open("result1.json", "r") as f:
    state = json.load(f)

state2 = {
    "working_event": e1,
    "message": state["message"][0],
}

result2 = node2.run(state2)


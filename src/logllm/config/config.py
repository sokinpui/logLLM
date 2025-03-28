# log configuration
LOGGER_NAME = 'MoveLookLogger'
LOG_FILE = 'movelook.log'

# Colima configuration
# in GB
COLIMA_MEMORY_SIZE = 4

# Docker configuration
# ==========================
# Docker network configuration
DOCKER_NETWORK_NAME = "movelook_network"

# Docker volume configuration
DOCKER_VOLUME_NAME = "movelook_volume"
DOCKER_VOLUME_BIND_PATH = "/usr/share/elasticsearch/data"
DOCKER_VOLUME_MODE = "rw"
DOCKER_VOLUME_SETUP = {
    DOCKER_VOLUME_NAME: {
        "bind": DOCKER_VOLUME_BIND_PATH,
        "mode": DOCKER_VOLUME_MODE
    }
}

# Elastic search configuration
ELASTIC_SEARCH_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:8.17.1"
ELASTIC_SEARCH_CONTAINER_NAME = "movelook_elastic_search"
ELASTIC_SEARCH_PORTS = {
        "9200/tcp": 9200,
}

ELASTIC_SEARCH_ENVIRONMENT = {
    "discovery.type": "single-node",
    "xpack.security.enabled": False,
    "xpack.license.self_generated.type": "trial"
}

ELASTIC_SEARCH_URL = f"http://localhost:9200"


# Kiabana configuration
KIBANA_IMAGE = "docker.elastic.co/kibana/kibana:8.17.1"
KIBANA_CONTAINER_NAME = "movelook_kibana"
KIBANA_PORTS = {
        "5601/tcp": 5601,
}

KIBANA_ENVIRONMENT = {
    "ELASTICSEARCH_HOSTS": f"http://{ELASTIC_SEARCH_CONTAINER_NAME}:9200"
}

# Volume configuration

# Docker container configuration
DOCKER_DETACH = True
DOCKER_REMOVE = False
DOCKER_PORTS_PROTOCOL = "tcp"

# ==========================

# Data storage ocnfiguration
# ==========================
## index name
INDEX_LAST_LINE_STATUS = "log_last_line_status"

INDEX_LOG_FILES_STORAGE = "log_files"

def get_log_stroage_index(group : str) -> str:
    """
    return log file index name that store log file for event_id
    """
    return f"log_{group}"

INDEX_EVENTS_STORAGE = "events"

INDEX_VECTOR_STORE = "vector_store"

# ==========================

# LLM model
# ==========================
# gemini model
# GEMINI_LLM_MODEL = "gemini-2.0-flash"
GEMINI_LLM_MODEL = "gemini-2.0-flash-lite"
# GEMINI_LLM_MODEL = "gemini-1.5-flash-8b"

# ==========================


# agents
# ==========================
# random sample size of log used in PreProcessAgent to generate search query, higher is better for accuracy, but computational time increase
RANDOM_SAMPLE_SIZE = 16

def get_pre_process_index(event_id : int) -> str:
    """
    return pre process index name that store filtered log for event_id
    """
    return f"pre_process_{event_id}"

# Maximum Memory context sie for analyze agent to store summary
MEMRORY_TOKENS_LIMIT = 20000
# ==========================


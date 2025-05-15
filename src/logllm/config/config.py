# log configuration
LOGGER_NAME = "MoveLookLogger"
LOG_FILE = "movelook.log"

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
    DOCKER_VOLUME_NAME: {"bind": DOCKER_VOLUME_BIND_PATH, "mode": DOCKER_VOLUME_MODE}
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
    "xpack.license.self_generated.type": "trial",
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


def get_log_storage_index(group: str) -> str:
    """
    Return the Elasticsearch index name where RAW logs for a group are stored.
    (Adjust logic based on how your Collector stores raw logs).
    Example: Assumes collector stores in 'log_<group_name>'
    """
    # Basic cleaning for index name compatibility
    clean_group = group.replace(" ", "_").replace("/", "_").replace(".", "_").lower()
    return f"log_{clean_group}"


INDEX_EVENTS_STORAGE = "events"

INDEX_VECTOR_STORE = "vector_store"

INDEX_GROUP_INFOS = "group_infos"

INDEX_GROK_RESULTS_HISTORY = "grok_results_history"

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


def get_pre_process_index(event_id: int) -> str:
    """
    return pre process index name that store filtered log for event_id
    """
    return f"pre_process_{event_id}"


def get_parsed_log_storage_index(group: str) -> str:
    """
    Generates an Elasticsearch index name for storing PARSED/STRUCTURED logs
    based on the original log group name.
    """
    # Ensure group name is filesystem/index friendly (basic cleaning)
    clean_group = group.replace(" ", "_").replace("/", "_").replace(".", "_").lower()
    return f"parsed_log_{clean_group}"


def get_unparsed_log_storage_index(group: str) -> str:
    """
    Generates an Elasticsearch index name for storing logs that failed parsing
    or were processed by fallback for a specific group.
    """
    clean_group = group.replace(" ", "_").replace("/", "_").replace(".", "_").lower()
    return f"unparsed_log_{clean_group}"


# Maximum Memory context sie for analyze agent to store summary
MEMRORY_TOKENS_LIMIT = 20000
# ==========================


# =========== timestamp normalizer ===============
def get_normalized_parsed_log_storage_index(group: str) -> str:
    """
    Generates an Elasticsearch index name for storing PARSED logs
    that have had their timestamps NORMALIZED.
    """
    clean_group = group.replace(" ", "_").replace("/", "_").replace(".", "_").lower()
    return f"normalized_parsed_log_{clean_group}"

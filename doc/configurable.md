# Detailed Documentation for `config.py`

## Overview
The `src/logllm/config/config.py` file contains centralized configuration settings and utility functions for the `logLLM` system. It defines constants and parameters for logging, Docker container management (via Colima on macOS or standard Docker), Elasticsearch, Kibana, data storage indices, LLM models, and agent-specific behaviors. These configurations are imported and utilized by various modules (e.g., CLI commands, agents, utilities) to ensure consistency and facilitate environment-specific adjustments.

---

## Configuration Variables

### Log Configuration
- **`LOGGER_NAME`**
  - **Type**: `str`
  - **Value**: `"MoveLookLogger"`
  - **Purpose**: Defines the name for the primary logger instance used throughout the application.
  - **Usage**: Used by `src.logllm.utils.logger.Logger` to identify the logger.
  - **Example**: `logger = Logger(name=cfg.LOGGER_NAME)`

- **`LOG_FILE`**
  - **Type**: `str`
  - **Value**: `"movelook.log"`
  - **Purpose**: Specifies the default file path where logs generated by the `Logger` instance are written.
  - **Usage**: Configures the `RotatingFileHandler` within the `Logger` class.
  - **Example**: Log messages are written to `movelook.log` in the directory where the script is run.

---

### Colima Configuration (macOS Docker Environment)
- **`COLIMA_MEMORY_SIZE`**
  - **Type**: `int`
  - **Value**: `4`
  - **Purpose**: Sets the default memory allocation (in Gigabytes) for the Colima virtual machine when it needs to be started (primarily relevant for macOS).
  - **Usage**: Used by the `db start` and `db restart` CLI commands (`src.logllm.cli.container`) via the `DockerManager` (`src.logllm.utils.container_manager`) to configure Colima if it's not already running. Can be overridden by the `-m`/`--memory` CLI flag.
  - **Example**: If Colima is stopped, `python -m src.logllm db start` would attempt `colima start --memory 4`.

---

### Docker Configuration (General)
- **`DOCKER_NETWORK_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_network"`
  - **Purpose**: Specifies the name of the Docker network created or used for inter-container communication (e.g., between Elasticsearch and Kibana).
  - **Usage**: Used by `DockerManager` (`_create_network`, `start_container`) to ensure containers are on the same network.
  - **Example**: `manager._create_network(cfg.DOCKER_NETWORK_NAME)`

- **`DOCKER_VOLUME_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_volume"`
  - **Purpose**: Defines the name of the Docker volume used for persisting Elasticsearch data.
  - **Usage**: Used by `DockerManager` (`_create_volume`, `start_container`) when setting up the Elasticsearch container.
  - **Example**: `manager._create_volume(cfg.DOCKER_VOLUME_NAME)`

- **`DOCKER_VOLUME_BIND_PATH`**
  - **Type**: `str`
  - **Value**: `"/usr/share/elasticsearch/data"`
  - **Purpose**: Specifies the path *inside* the Elasticsearch container where the persistent volume (`DOCKER_VOLUME_NAME`) should be mounted.
  - **Usage**: Part of the `DOCKER_VOLUME_SETUP` dictionary.
  - **Example**: Ensures Elasticsearch data is written to the persistent volume.

- **`DOCKER_VOLUME_MODE`**
  - **Type**: `str`
  - **Value**: `"rw"`
  - **Purpose**: Sets the access mode for the mounted volume (read-write).
  - **Usage**: Part of the `DOCKER_VOLUME_SETUP` dictionary. Ensures the Elasticsearch container can write data.

- **`DOCKER_VOLUME_SETUP`**
  - **Type**: `dict`
  - **Value**: `{ cfg.DOCKER_VOLUME_NAME: { "bind": cfg.DOCKER_VOLUME_BIND_PATH, "mode": cfg.DOCKER_VOLUME_MODE } }`
  - **Purpose**: Consolidates the volume configuration into a dictionary format expected by the `docker-py` library.
  - **Usage**: Passed to `DockerManager.start_container` for the Elasticsearch service.

- **`DOCKER_DETACH`**
  - **Type**: `bool`
  - **Value**: `True`
  - **Purpose**: Determines if Docker containers should be run in detached mode (in the background).
  - **Usage**: Passed to `DockerManager.start_container`. `True` is typical for service containers.

- **`DOCKER_REMOVE`**
  - **Type**: `bool`
  - **Value**: `False`
  - **Purpose**: Controls whether Docker containers should be automatically removed when they stop/exit.
  - **Usage**: Passed to `DockerManager.start_container`. Setting to `False` allows inspection of stopped containers. Can be overridden by `db stop --remove`.

- **`DOCKER_PORTS_PROTOCOL`**
  - **Type**: `str`
  - **Value**: `"tcp"`
  - **Purpose**: Specifies the default network protocol for port mappings (currently implicitly used by the `docker-py` format).
  - **Usage**: Defines the protocol part of port specifications like `"9200/tcp"`.

---

### Elasticsearch Configuration
- **`ELASTIC_SEARCH_IMAGE`**
  - **Type**: `str`
  - **Value**: `"docker.elastic.co/elasticsearch/elasticsearch:8.17.1"`
  - **Purpose**: The specific Docker image tag for Elasticsearch to be used.
  - **Usage**: Used by `DockerManager` to pull and run the Elasticsearch container via the `db` command.

- **`ELASTIC_SEARCH_CONTAINER_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_elastic_search"`
  - **Purpose**: Sets a consistent name for the Elasticsearch Docker container, used for management and inter-container communication (e.g., by Kibana).
  - **Usage**: Used by `DockerManager` and referenced in `KIBANA_ENVIRONMENT`.

- **`ELASTIC_SEARCH_PORTS`**
  - **Type**: `dict`
  - **Value**: `{"9200/tcp": 9200}`
  - **Purpose**: Defines the port mapping for Elasticsearch. Maps port 9200 inside the container to port 9200 on the host machine.
  - **Usage**: Passed to `DockerManager.start_container`. Allows access to Elasticsearch API from the host.

- **`ELASTIC_SEARCH_ENVIRONMENT`**
  - **Type**: `dict`
  - **Value**: `{"discovery.type": "single-node", "xpack.security.enabled": "false", "xpack.license.self_generated.type": "trial"}`
  - **Purpose**: Sets essential environment variables within the Elasticsearch container for simplified setup (single node, security disabled for development/testing, trial license). Note: Security should be enabled in production.
  - **Usage**: Passed to `DockerManager.start_container`.

- **`ELASTIC_SEARCH_URL`**
  - **Type**: `str`
  - **Value**: `"http://localhost:9200"`
  - **Purpose**: The default URL used by the `ElasticsearchDatabase` utility (`src.logllm.utils.database`) to connect to the Elasticsearch instance.
  - **Usage**: `Elasticsearch([cfg.ELASTIC_SEARCH_URL])`

---

### Kibana Configuration
- **`KIBANA_IMAGE`**
  - **Type**: `str`
  - **Value**: `"docker.elastic.co/kibana/kibana:8.17.1"`
  - **Purpose**: The specific Docker image tag for Kibana.
  - **Usage**: Used by `DockerManager` to pull and run the Kibana container via the `db` command.

- **`KIBANA_CONTAINER_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_kibana"`
  - **Purpose**: Sets a consistent name for the Kibana Docker container.
  - **Usage**: Used by `DockerManager` for management.

- **`KIBANA_PORTS`**
  - **Type**: `dict`
  - **Value**: `{"5601/tcp": 5601}`
  - **Purpose**: Defines the port mapping for Kibana. Maps port 5601 inside the container to port 5601 on the host machine.
  - **Usage**: Passed to `DockerManager.start_container`. Allows access to the Kibana web UI from the host.

- **`KIBANA_ENVIRONMENT`**
  - **Type**: `dict`
  - **Value**: `{"ELASTICSEARCH_HOSTS": f"http://{cfg.ELASTIC_SEARCH_CONTAINER_NAME}:9200"}`
  - **Purpose**: Configures the Kibana container to connect to the Elasticsearch container using its container name within the Docker network.
  - **Usage**: Passed to `DockerManager.start_container`. Essential for Kibana to function.

---

### Data Storage Configuration (Elasticsearch Indices)
- **`INDEX_LAST_LINE_STATUS`**
  - **Type**: `str`
  - **Value**: `"log_last_line_status"`
  - **Purpose**: Names the Elasticsearch index used by the `Collector` utility (`src.logllm.utils.collector`) to track the last line number processed for each log file, enabling incremental updates.
  - **Usage**: `db.update(index=cfg.INDEX_LAST_LINE_STATUS, ...)`

- **`INDEX_LOG_FILES_STORAGE`**
  - **Type**: `str`
  - **Value**: `"log_files"`
  - **Purpose**: Default base index name for storing raw log file entries. Note: Often superseded by group-specific indices generated by `get_log_storage_index`.
  - **Usage**: May be used in queries if group-specific indexing isn't employed or for global metadata.

- **`INDEX_EVENTS_STORAGE`**
  - **Type**: `str`
  - **Value**: `"events"`
  - **Purpose**: Names the Elasticsearch index used for storing event descriptions or related metadata (if applicable to the workflow).
  - **Usage**: Potentially used by analysis agents.

- **`INDEX_VECTOR_STORE`**
  - **Type**: `str`
  - **Value**: `"vector_store"`
  - **Purpose**: Base prefix for Elasticsearch indices used as vector stores by the `RAGManager` (`src.logllm.utils.rag_manager`). A specific name is appended (e.g., `"vector_store_docs"`).
  - **Usage**: `index_name=f"{cfg.INDEX_VECTOR_STORE}_{rag_instance_name}"`

- **`INDEX_GROUP_INFOS`**
  - **Type**: `str`
  - **Value**: `"group_infos"`
  - **Purpose**: Names the Elasticsearch index where the `Collector` stores information about discovered log groups and their associated file paths.
  - **Usage**: Used by `GroupLogParserAgent` (`src.logllm.agents.parser_agent`) and `AllGroupsParserAgent` (`src.logllm.agents.es_parser_agent`) to determine which files/groups to parse.

- **`INDEX_GROK_RESULTS_HISTORY`**
  - **Type**: `str`
  - **Value**: `"grok_results_history"`
  - **Purpose**: Names the Elasticsearch index where `SingleGroupParserAgent` stores a summary of each Grok parsing run (status, pattern used, counts).
  - **Usage**: Queried by `es-parse list` command. Written to by `SingleGroupParserAgent`.

---

### LLM Model Configuration
- **`GEMINI_LLM_MODEL`**
  - **Type**: `str`
  - **Value**: `"gemini-1.5-flash-latest"` (Example value, was `gemini-2.0-flash-lite` previously)
  - **Purpose**: Specifies the default Gemini model identifier to be used by `GeminiModel` (`src.logllm.utils.llm_model`). Select appropriate models based on availability and needs (cost, performance, context window).
  - **Usage**: `genai.GenerativeModel(model_name=cfg.GEMINI_LLM_MODEL)`
  - **Note**: Other valid model names (like `gemini-1.5-pro-latest`, `gemini-1.5-flash-latest`) can be used. Check Google AI documentation for current models.

---

### Agents Configuration
- **`RANDOM_SAMPLE_SIZE`**
  - **Type**: `int`
  - **Value**: `16`
  - **Purpose**: Defines the default number of log lines to sample when generating context for LLM-based tasks like query generation or pattern generation (used in older `PreProcessAgent` concept and potentially reused).
  - **Usage**: Can influence the quality of LLM generation; higher values provide more context but increase token usage and latency.

- **`MEMRORY_TOKENS_LIMIT`**
  - **Type**: `int`
  - **Value**: `20000`
  - **Purpose**: Sets a token limit for context or memory accumulation within agents (e.g., summarizing previous analysis in `LinearAnalyzeAgent` concept).
  - **Usage**: Helps manage context window limitations of LLMs during long-running analysis tasks.

---

## Utility Functions for Index Naming

### Function: `get_log_storage_index(group: str) -> str`
- **Purpose**: Generates a standardized Elasticsearch index name for storing **raw** log entries belonging to a specific group.
- **Parameters**: `group` (str): The name of the log group (e.g., "apache", "hadoop").
- **Returns**: `str`: An index name like `"log_apache"`, `"log_hadoop"`. Cleans the group name for index compatibility.
- **Usage**: Used by `Collector` (`insert_very_large_logs_into_db`) to direct raw logs to the correct index. Also used by parsing agents (`es-parse`, `parse`) to identify source indices.

### Function: `get_pre_process_index(event_id: int) -> str`
- **Purpose**: Generates a standardized index name for storing intermediate, filtered log data related to a specific analysis event (used in older agent concepts, may be less relevant now).
- **Parameters**: `event_id` (int): The numeric ID of the event being processed.
- **Returns**: `str`: An index name like `"pre_process_1"`.
- **Usage**: Intended for agents that filter logs based on events before detailed analysis.

### Function: `get_parsed_log_storage_index(group: str) -> str` # <-- NEW
- **Purpose**: Generates a standardized Elasticsearch index name for storing **successfully parsed/structured** log data for a specific group.
- **Parameters**: `group` (str): The name of the original log group.
- **Returns**: `str`: An index name like `"parsed_log_apache"`, `"parsed_log_hadoop"`. Cleans the group name.
- **Usage**: Used by `es-parse` (`SingleGroupParserAgent` via `ScrollGrokParserAgent`) as the target index for successfully processed documents.

### Function: `get_unparsed_log_storage_index(group: str) -> str` # <-- NEW
- **Purpose**: Generates a standardized Elasticsearch index name for storing log entries that **failed parsing** or were processed using a **fallback** mechanism for a specific group.
- **Parameters**: `group` (str): The name of the original log group.
- **Returns**: `str`: An index name like `"unparsed_log_apache"`, `"unparsed_log_hadoop"`. Cleans the group name.
- **Usage**: Used by `es-parse` (`SingleGroupParserAgent` via `ScrollGrokParserAgent`) as the target index for documents that couldn't be parsed with the primary pattern or were handled by fallback. Allows separation of problematic logs.


# Detailed Documentation for `config.py`

## Overview
The `config.py` file contains configuration settings and utility functions for the log analysis system. It defines constants for logging, Docker, Elasticsearch, Kibana, data storage, LLM models, and agent-specific settings. These configurations are imported and used by other modules (e.g., `llm_model.py`, `database.py`, `collector.py`) to ensure consistency across the application.

---

## Configuration Variables

### Log Configuration
- **`LOGGER_NAME`**
  - **Type**: `str`
  - **Value**: `"MoveLookLogger"`
  - **Purpose**: Defines the name of the logger instance used throughout the application.
  - **Usage**: Passed to the `Logger` class in `logger.py` to identify the logger.
  - **Example**: `Logger(name=cfg.LOGGER_NAME)`

- **`LOG_FILE`**
  - **Type**: `str`
  - **Value**: `"movelook.log"`
  - **Purpose**: Specifies the file path where logs are written.
  - **Usage**: Used by the `Logger` class to configure the file handler.
  - **Example**: Logs are written to `movelook.log` in the current directory.

---

### Colima Configuration
- **`COLIMA_MEMORY_SIZE`**
  - **Type**: `int`
  - **Value**: `4`
  - **Purpose**: Sets the memory size (in GB) allocated to the Colima Docker runtime on macOS.
  - **Usage**: Used in `container_manger.py` to start Colima with a specific memory limit.
  - **Example**: `subprocess.run(['colima', 'start', '--memory', str(cfg.COLIMA_MEMORY_SIZE)])`

---

### Docker Configuration
- **`DOCKER_NETWORK_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_network"`
  - **Purpose**: Defines the name of the Docker network used for container communication.
  - **Usage**: Passed to `DockerManager` in `container_manger.py` to create or connect containers to this network.
  - **Example**: `elastic_manager._create_network(cfg.DOCKER_NETWORK_NAME)`

- **`DOCKER_VOLUME_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_volume"`
  - **Purpose**: Specifies the name of the Docker volume for persistent storage.
  - **Usage**: Used to configure volume setup in `DockerManager`.
  - **Example**: `elastic_manager._create_volume(cfg.DOCKER_VOLUME_NAME)`

- **`DOCKER_VOLUME_BIND_PATH`**
  - **Type**: `str`
  - **Value**: `"/usr/share/elasticsearch/data"`
  - **Purpose**: Defines the container path where the volume is mounted for Elasticsearch data.
  - **Usage**: Part of the volume setup dictionary.
  - **Example**: Maps the volume to Elasticsearch’s data directory.

- **`DOCKER_VOLUME_MODE`**
  - **Type**: `str`
  - **Value**: `"rw"`
  - **Purpose**: Sets the volume access mode (read-write).
  - **Usage**: Ensures the volume is writable by the container.
  - **Example**: Allows Elasticsearch to write logs to the volume.

- **`DOCKER_VOLUME_SETUP`**
  - **Type**: `dict`
  - **Value**:
    ```python
    {
        DOCKER_VOLUME_NAME: {
            "bind": DOCKER_VOLUME_BIND_PATH,
            "mode": DOCKER_VOLUME_MODE
        }
    }
    ```
  - **Purpose**: Configures the volume binding for Docker containers.
  - **Usage**: Passed to `start_container` in `DockerManager` to set up persistent storage.
  - **Example**: `elastic_manager.start_container(volume_setup=cfg.DOCKER_VOLUME_SETUP)`

- **`DOCKER_DETACH`**
  - **Type**: `bool`
  - **Value**: `True`
  - **Purpose**: Indicates whether containers run in detached mode (background).
  - **Usage**: Controls container behavior in `DockerManager`.
  - **Example**: `elastic_manager.start_container(detach=cfg.DOCKER_DETACH)`

- **`DOCKER_REMOVE`**
  - **Type**: `bool`
  - **Value**: `False`
  - **Purpose**: Determines if containers are automatically removed after stopping.
  - **Usage**: Configures cleanup behavior in `DockerManager`.
  - **Example**: Keeps containers for debugging if set to `False`.

- **`DOCKER_PORTS_PROTOCOL`**
  - **Type**: `str`
  - **Value**: `"tcp"`
  - **Purpose**: Specifies the protocol for port mappings (currently unused in code but reserved).
  - **Usage**: Could be used in future port configuration enhancements.
  - **Example**: N/A (not directly applied in provided code).

---

### Elasticsearch Configuration
- **`ELASTIC_SEARCH_IMAGE`**
  - **Type**: `str`
  - **Value**: `"docker.elastic.co/elasticsearch/elasticsearch:8.17.1"`
  - **Purpose**: Specifies the Docker image for Elasticsearch.
  - **Usage**: Used by `DockerManager` to pull and run the Elasticsearch container.
  - **Example**: `elastic_manager._pull_image(cfg.ELASTIC_SEARCH_IMAGE)`

- **`ELASTIC_SEARCH_CONTAINER_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_elastic_search"`
  - **Purpose**: Names the Elasticsearch container.
  - **Usage**: Ensures a consistent container name for management.
  - **Example**: `elastic_manager.start_container(name=cfg.ELASTIC_SEARCH_CONTAINER_NAME)`

- **`ELASTIC_SEARCH_PORTS`**
  - **Type**: `dict`
  - **Value**: `{"9200/tcp": 9200}`
  - **Purpose**: Maps Elasticsearch’s port 9200 to the host.
  - **Usage**: Configures port forwarding in `DockerManager`.
  - **Example**: Access Elasticsearch at `http://localhost:9200`.

- **`ELASTIC_SEARCH_ENVIRONMENT`**
  - **Type**: `dict`
  - **Value**:
    ```python
    {
        "discovery.type": "single-node",
        "xpack.security.enabled": False,
        "xpack.license.self_generated.type": "trial"
    }
    ```
  - **Purpose**: Sets environment variables for Elasticsearch to run as a single node without security (for development).
  - **Usage**: Passed to `start_container` to configure Elasticsearch.
  - **Example**: Simplifies setup for testing.

- **`ELASTIC_SEARCH_URL`**
  - **Type**: `str`
  - **Value**: `"http://localhost:9200"`
  - **Purpose**: Defines the URL to connect to Elasticsearch.
  - **Usage**: Used by `ElasticsearchDatabase` to establish a connection.
  - **Example**: `requests.get(cfg.ELASTIC_SEARCH_URL)`

---

### Kibana Configuration
- **`KIBANA_IMAGE`**
  - **Type**: `str`
  - **Value**: `"docker.elastic.co/kibana/kibana:8.17.1"`
  - **Purpose**: Specifies the Docker image for Kibana.
  - **Usage**: Used by `DockerManager` to run the Kibana container.
  - **Example**: `kibana_manager._pull_image(cfg.KIBANA_IMAGE)`

- **`KIBANA_CONTAINER_NAME`**
  - **Type**: `str`
  - **Value**: `"movelook_kibana"`
  - **Purpose**: Names the Kibana container.
  - **Usage**: Ensures a consistent container name.
  - **Example**: `kibana_manager.start_container(name=cfg.KIBANA_CONTAINER_NAME)`

- **`KIBANA_PORTS`**
  - **Type**: `dict`
  - **Value**: `{"5601/tcp": 5601}`
  - **Purpose**: Maps Kibana’s port 5601 to the host.
  - **Usage**: Configures port forwarding for Kibana access.
  - **Example**: Access Kibana at `http://localhost:5601`.

- **`KIBANA_ENVIRONMENT`**
  - **Type**: `dict`
  - **Value**:
    ```python
    {"ELASTICSEARCH_HOSTS": f"http://{ELASTIC_SEARCH_CONTAINER_NAME}:9200"}
    ```
  - **Purpose**: Links Kibana to Elasticsearch.
  - **Usage**: Ensures Kibana can communicate with the Elasticsearch container.
  - **Example**: Configures Kibana to use the Elasticsearch instance running in the same network.

---

### Data Storage Configuration
- **`INDEX_LAST_LINE_STATUS`**
  - **Type**: `str`
  - **Value**: `"log_last_line_status"`
  - **Purpose**: Names the Elasticsearch index for tracking the last line read of log files.
  - **Usage**: Used by `Collector` to store and retrieve last line read data.
  - **Example**: `db.single_search(query, cfg.INDEX_LAST_LINE_STATUS)`

- **`INDEX_LOG_FILES_STORAGE`**
  - **Type**: `str`
  - **Value**: `"log_files"`
  - **Purpose**: Default index name for storing log file data (though often overridden by `get_log_stroage_index`).
  - **Usage**: Used in `LogFile` and `Collector` for log storage.
  - **Example**: `log.get_total_lines(db)` queries this index.

- **`INDEX_EVENTS_STORAGE`**
  - **Type**: `str`
  - **Value**: `"events"`
  - **Purpose**: Names the Elasticsearch index for storing event data.
  - **Usage**: Used by `Collector` to store events.
  - **Example**: `collector.insert_events_to_db(db, events)`

- **`INDEX_VECTOR_STORE`**
  - **Type**: `str`
  - **Value**: `"vector_store"`
  - **Purpose**: Base name for vector store indices used by `RAGManager`.
  - **Usage**: Combined with a name to create unique vector store indices.
  - **Example**: `f"{cfg.INDEX_VECTOR_STORE}_{name}"`

---

### LLM Model Configuration
- **`GEMINI_LLM_MODEL`**
  - **Type**: `str`
  - **Value**: `"gemini-2.0-flash-lite"`
  - **Purpose**: Specifies the Gemini model variant to use.
  - **Usage**: Passed to `GeminiModel` to initialize the correct model.
  - **Example**: `ChatGoogleGenerativeAI(model=cfg.GEMINI_LLM_MODEL)`
  - **Note**: Other options (e.g., `"gemini-2.0-flash"`, `"gemini-1.5-flash-8b"`) are commented out but available.

---

### Agents Configuration
- **`RANDOM_SAMPLE_SIZE`**
  - **Type**: `int`
  - **Value**: `16`
  - **Purpose**: Sets the number of random log samples used by the `PreProcessAgent` to generate search queries.
  - **Usage**: Balances accuracy and computational cost in log analysis agents.
  - **Example**: `db.random_sample("log_files", cfg.RANDOM_SAMPLE_SIZE)`

- **`MEMRORY_TOKENS_LIMIT`**
  - **Type**: `int`
  - **Value**: `20000`
  - **Purpose**: Defines the maximum token limit for the analysis agent’s memory context.
  - **Usage**: Limits the summary size stored by agents to manage memory usage.
  - **Example**: Ensures summaries fit within the model’s context window.

---

## Utility Functions

### Function: `get_log_stroage_index(group: str) -> str`
- **Purpose**: Generates a log storage index name based on a group identifier.
- **Parameters**:
  - `group` (str): The group or parent directory name of the logs (e.g., from `LogFile.belongs_to`).
- **Returns**: `str` - An index name in the format `"log_{group}"`.
- **Usage**: Used by `Collector` to store logs in group-specific indices.
- **Example**:
  - Input: `get_log_stroage_index("ssh_logs")`
  - Output: `"log_ssh_logs"`
- **Context**: Allows logs to be organized by their source group in Elasticsearch.

### Function: `get_pre_process_index(event_id: int) -> str`
- **Purpose**: Generates a pre-process index name for filtered logs associated with a specific event.
- **Parameters**:
  - `event_id` (int): The ID of the event.
- **Returns**: `str` - An index name in the format `"pre_process_{event_id}"`.
- **Usage**: Used by agents (e.g., `PreProcessAgent`) to store filtered log data for analysis.
- **Example**:
  - Input: `get_pre_process_index(1)`
  - Output: `"pre_process_1"`
- **Context**: Facilitates event-specific log preprocessing in multi-agent workflows.

---

## Usage Notes
- **Customization**: Modify these values to adapt the system to different environments (e.g., change `ELASTIC_SEARCH_URL` for a remote server).
- **Environment Variables**: Ensure `GENAI_API_KEY` is set for `GeminiModel` to work.
- **Docker Setup**: The Docker configurations assume a local setup; adjust ports or network names if running on a different host.
- **Index Naming**: The dynamic index functions (`get_log_stroage_index`, `get_pre_process_index`) help manage multiple log groups and events, making the system scalable.
- **Dependencies**: Values like `ELASTIC_SEARCH_CONTAINER_NAME` in `KIBANA_ENVIRONMENT` must match the actual container name for network communication to work.

# Container Manager Utility (`container_manager.py`)

## File: `src/logllm/utils/container_manager.py`

### Overview

Manages Docker containers, primarily for setting up the Elasticsearch and Kibana environment. Includes logic for handling different operating systems (macOS via Colima, Linux, basic Windows check).

### Class: `ContainerManager(ABC)`

- **Purpose**: Abstract base class for container management.
- **Abstract Methods**: `remove_container` (and potentially others like start, stop, status if formalized).

### Class: `DockerManager(ContainerManager)`

- **Purpose**: Concrete implementation using `docker-py` to interact with the Docker daemon.
- **Key Methods**:
  - **`__init__(self)`**: Initializes logger. Client is initialized lazily by `_ensure_client`.
  - **`_ensure_client(self, memory_gb: Optional[int] = None) -> bool`**: Checks if the client is initialized. If not, calls `_start_daemon` (passing `memory_gb`). Returns `True` if client is ready.
  - **`_start_daemon(self, memory_gb: Optional[int] = None) -> Optional[docker.client.DockerClient]`**: Detects OS. On macOS, checks Colima status, starts it if necessary (using `memory_gb` or `cfg.COLIMA_MEMORY_SIZE`), sets `DOCKER_HOST`, and returns a client. On Linux/Windows, attempts direct connection assuming daemon/Desktop is running.
  - **`start_container(self, name: str, image: str, ..., memory_gb: int = 4) -> Optional[str]`**: Starts a container. Ensures client is ready via `_ensure_client` (passing `memory_gb`), removes existing container with the same name, pulls image if needed, creates network/volume if needed (via internal methods), and runs the container. Returns container ID or `None`.
  - **`stop_container(self, name: str) -> bool`**: Stops a running container by name.
  - **`remove_container(self, name: str) -> bool`**: Forcefully removes a container by name.
  - **`get_container_status(self, name: str) -> str`**: Returns the status ('running', 'exited', 'not found', 'error') of a container.
  - **`_remove_container_if_exists(self, container_name: str)`**: Helper to stop and remove a container by name if it exists.
  - **`_create_network(self, network_name: str)`**: Creates Docker network if it doesn't exist.
  - **`_create_volume(self, volume_name: str)`**: Creates Docker volume if it doesn't exist.
  - **`_pull_image(self, image: str) -> None`**: Pulls Docker image if not found locally.

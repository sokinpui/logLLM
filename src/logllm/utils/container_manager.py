# src/logllm/utils/container_manager.py

from abc import ABC, abstractmethod
import platform
import subprocess
import os
import docker
from docker.errors import NotFound, APIError
from typing import Optional # Added Optional

from .logger import Logger
from ..config import config as cfg


class ContainerManager(ABC):
    # ... (abstract methods) ...
    @abstractmethod
    def remove_container(self, name: str) -> bool: # Add remove abstract method
        pass


class DockerManager(ContainerManager):

    def __init__(self):
        self._logger = Logger()
        # Start daemon moved to specific actions needing it
        self._client: Optional[docker.client.DockerClient] = None
        self.id = None

    def _ensure_client(self, memory_gb: Optional[int] = None) -> bool:
        """Initializes the Docker client if not already done."""
        if self._client is None:
            self._client = self._start_daemon(memory_gb=memory_gb) # Pass memory here
        return self._client is not None

    def start_container(self,
                        name: str,
                        image: str,
                        network: str,
                        volume_setup: dict,
                        ports: dict,
                        env_vars: dict,
                        detach: bool,
                        remove: bool,
                        memory_gb: int = 4 # Added memory for daemon start
                        ) -> Optional[str]: # Return type hint

        # Ensure Docker client is initialized (and potentially Colima started)
        if not self._ensure_client(memory_gb=memory_gb):
             self._logger.error("Failed to initialize Docker client. Cannot start container.")
             return None

        self._remove_container_if_exists(name) # Changed method name for clarity

        try:
            self._logger.info(f"Attempting to run container '{name}'...")
            container = self._client.containers.run(
                name=name,
                image=image,
                network=network,
                volumes=volume_setup,
                ports=ports,
                environment=env_vars,
                detach=detach,
                remove=remove # If True, container is removed on stop/exit
            )
            self._logger.info(f"Container {name}:{container.short_id} started successfully.")
            return container.id

        except APIError as api_err:
             self._logger.error(f"Docker API error starting container {name}: {api_err}")
             if "port is already allocated" in str(api_err):
                  self._logger.error(f"Port conflict: Check if ports {ports.values()} are already in use.")
             elif "container name" in str(api_err) and "is already in use" in str(api_err):
                 self._logger.error(f"Container name conflict: Container '{name}' might still exist despite removal attempt.")
             return None
        except Exception as e:
            self._logger.error(f"Generic error starting container {name}: {e}", exc_info=True)
            return None

    def stop_container(self, name: str) -> bool:
        """Stops a running container by name."""
        if not self._ensure_client(): return False # Ensure client is ready

        try:
            self._logger.info(f"Attempting to stop container '{name}'...")
            container = self._client.containers.get(name)
            container.stop()
            self._logger.info(f"Container '{name}' stopped successfully.")
            return True
        except NotFound:
            self._logger.warning(f"Container '{name}' not found, cannot stop.")
            return False # Or True if "not found" means "already stopped"? False is safer.
        except APIError as api_err:
             self._logger.error(f"Docker API error stopping container {name}: {api_err}")
             return False
        except Exception as e:
            self._logger.error(f"Generic error stopping container {name}: {e}", exc_info=True)
            return False

    def remove_container(self, name: str) -> bool:
        """Removes a container by name (forcefully)."""
        if not self._ensure_client(): return False # Ensure client is ready

        try:
            self._logger.info(f"Attempting to remove container '{name}'...")
            container = self._client.containers.get(name)
            container.remove(force=True)
            self._logger.info(f"Container '{name}' removed successfully.")
            return True
        except NotFound:
            self._logger.warning(f"Container '{name}' not found, cannot remove.")
            return False # Or True if not found means already removed? False is safer.
        except APIError as api_err:
             self._logger.error(f"Docker API error removing container {name}: {api_err}")
             return False
        except Exception as e:
            self._logger.error(f"Generic error removing container {name}: {e}", exc_info=True)
            return False

    # Renamed for clarity
    def _remove_container_if_exists(self, container_name: str):
        """Stops and removes a container if it exists."""
        if not self._ensure_client(): return # Cannot do anything without client

        try:
            container = self._client.containers.get(container_name)
            self._logger.info(f"Container '{container_name}' found. Stopping and removing...")
            try:
                container.stop()
            except APIError as stop_err:
                 # Log stop error but proceed to remove if possible
                 self._logger.warning(f"Error stopping container {container_name} before removal: {stop_err}")
            container.remove(force=True)
            self._logger.info(f"Container '{container_name}' removed.")
        except NotFound:
            self._logger.info(f"Container '{container_name}' not found, no removal needed.")
        except APIError as api_err:
             self._logger.error(f"Docker API error trying to remove container {container_name}: {api_err}")
        except Exception as e:
            self._logger.error(f"Generic error removing container {container_name}: {e}", exc_info=True)


    def get_container_status(self, name: str) -> str:
        """Gets the status of a container by name."""
        if not self._ensure_client(): return "error (client init failed)"

        try:
            container = self._client.containers.get(name)
            return container.status
        except NotFound:
            return "not found"
        except APIError as api_err:
             self._logger.error(f"Docker API error getting status for {name}: {api_err}")
             return "error (api)"
        except Exception as e:
            self._logger.error(f"Generic error getting status for {name}: {e}", exc_info=True)
            return "error (general)"

    def _create_network(self, network_name : str):
        if not self._ensure_client(): return
        try:
            self._client.networks.get(network_name)
            self._logger.info(f"Network '{network_name}' already exists.")
        except NotFound:
            self._logger.info(f"Network '{network_name}' not found. Creating...")
            try:
                self._client.networks.create(network_name, driver="bridge")
                self._logger.info(f"Network '{network_name}' created successfully.")
            except APIError as api_err:
                 self._logger.error(f"Docker API error creating network {network_name}: {api_err}")
            except Exception as e:
                 self._logger.error(f"Error creating network {network_name}: {e}", exc_info=True)
        except APIError as api_err:
             self._logger.error(f"Docker API error checking network {network_name}: {api_err}")
        except Exception as e:
            self._logger.error(f"Error checking network {network_name}: {e}", exc_info=True)


    def _create_volume(self, volume_name : str):
        if not self._ensure_client(): return
        try:
            self._client.volumes.get(volume_name)
            self._logger.info(f"Volume '{volume_name}' already exists.")
        except NotFound:
            self._logger.info(f"Volume '{volume_name}' not found. Creating...")
            try:
                self._client.volumes.create(volume_name)
                self._logger.info(f"Volume '{volume_name}' created successfully.")
            except APIError as api_err:
                 self._logger.error(f"Docker API error creating volume {volume_name}: {api_err}")
            except Exception as e:
                 self._logger.error(f"Error creating volume {volume_name}: {e}", exc_info=True)
        except APIError as api_err:
             self._logger.error(f"Docker API error checking volume {volume_name}: {api_err}")
        except Exception as e:
            self._logger.error(f"Error checking volume {volume_name}: {e}", exc_info=True)


    def _pull_image(self, image : str) -> None:
        if not self._ensure_client(): return
        try:
            self._client.images.get(image)
            self._logger.info(f"Image '{image}' already exists locally.")
        except docker.errors.ImageNotFound:
            self._logger.info(f"Image '{image}' not found locally. Pulling...")
            try:
                self._client.images.pull(image)
                self._logger.info(f"Image '{image}' pulled successfully.")
            except APIError as api_err:
                self._logger.error(f"Docker API error pulling image {image}: {api_err}")
            except Exception as e:
                self._logger.error(f"Error pulling image {image}: {e}", exc_info=True)
        except APIError as api_err:
             self._logger.error(f"Docker API error checking image {image}: {api_err}")
        except Exception as e:
            self._logger.error(f"Error checking image {image}: {e}", exc_info=True)

    # Modified to accept memory argument
    def _start_daemon(self, memory_gb: Optional[int] = None) -> Optional[docker.client.DockerClient]:
        system = platform.system()
        self._logger.info(f"Detected system: {system}")

        if system == "Windows":
            self._logger.error("Docker daemon management (like Colima) is not supported automatically on Windows.")
            # Try connecting directly assuming Docker Desktop is running
            try:
                client = docker.from_env()
                client.ping() # Test connection
                self._logger.info("Successfully connected to Docker daemon (likely Docker Desktop).")
                return client
            except Exception as e:
                self._logger.error(f"Failed to connect to Docker daemon on Windows: {e}. Ensure Docker Desktop is running.")
                return None

        elif system == "Linux":
             # Assume Docker daemon is managed by systemd or similar
             try:
                client = docker.from_env()
                client.ping() # Test connection
                self._logger.info("Successfully connected to Docker daemon on Linux.")
                return client
             except Exception as e:
                 self._logger.error(f"Failed to connect to Docker daemon on Linux: {e}. Ensure Docker service is running and user has permissions.")
                 return None

        elif system == "Darwin": # MacOS
            self._logger.info("Attempting to manage Docker daemon via Colima on MacOS.")
            try:
                # Check Colima status
                res = subprocess.run(["colima", "status"], capture_output=True, text=True, check=False)
                is_running = 'Running' in res.stdout and 'level=fatal' not in res.stderr

                if not is_running:
                    self._logger.info("Colima is not running. Attempting to start Colima...")
                    # Use provided memory or default from config
                    effective_memory_gb = memory_gb if memory_gb is not None else cfg.COLIMA_MEMORY_SIZE
                    colima_memory_size = str(effective_memory_gb)
                    self._logger.info(f"Using Colima memory size: {colima_memory_size}GB")
                    start_cmd = ['colima', 'start', '--memory', colima_memory_size]
                    # Consider adding '--arch', etc., if needed based on config
                    start_res = subprocess.run(start_cmd, check=True, capture_output=True, text=True)
                    self._logger.info("Colima started successfully.")
                    self._logger.debug(f"Colima start output:\n{start_res.stdout}\n{start_res.stderr}")
                else:
                    self._logger.info("Colima is already running.")

                # Set DOCKER_HOST environment variable for docker-py
                home_dir = os.getenv('HOME')
                if not home_dir:
                    self._logger.error("Could not determine HOME directory.")
                    return None
                docker_sock_path = f'unix://{home_dir}/.colima/default/docker.sock'
                os.environ['DOCKER_HOST'] = docker_sock_path
                self._logger.debug(f"Set DOCKER_HOST to: {docker_sock_path}")

                # Connect using updated environment
                client = docker.from_env()
                client.ping() # Verify connection
                self._logger.info("Successfully connected to Docker daemon via Colima socket.")
                return client

            except FileNotFoundError:
                 self._logger.error("Colima command not found. Please install Colima (brew install colima).")
                 return None
            except subprocess.CalledProcessError as cpe:
                 self._logger.error(f"Error executing Colima command: {cpe}")
                 self._logger.error(f"Colima stderr:\n{cpe.stderr}")
                 return None
            except Exception as e:
                self._logger.error(f"Error managing Colima or connecting to Docker daemon: {e}", exc_info=True)
                return None
        else:
             self._logger.error(f"Unsupported operating system: {system}")
             return None

# Remove the main() block from container_manager.py
# if __name__ == "__main__":
#    main()

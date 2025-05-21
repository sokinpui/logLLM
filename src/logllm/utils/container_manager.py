# src/logllm/utils/container_manager.py

import os
import platform
import subprocess
from abc import ABC, abstractmethod
from typing import Optional  # Added Optional

import docker
from docker.errors import APIError, NotFound

from .logger import Logger


class ContainerManager(ABC):
    # ... (abstract methods) ...
    @abstractmethod
    def remove_container(self, name: str) -> bool:  # Add remove abstract method
        pass


class DockerManager(ContainerManager):
    def __init__(self):
        self._logger = Logger()
        self._client: Optional[docker.client.DockerClient] = None
        self.id = None  # This attribute 'id' is initialized but not used. Consider removing if truly unused.

    def _ensure_client(self) -> bool:
        """Initializes the Docker client if not already done by attempting to connect to a running daemon."""
        if self._client is None:
            self._client = self._start_daemon()
        return self._client is not None

    def start_container(
        self,
        name: str,
        image: str,
        network: str,
        volume_setup: dict,
        ports: dict,
        env_vars: dict,
        detach: bool,
        remove: bool,
        # memory_gb: int = 4, # Removed memory_gb as it was for Colima
    ) -> Optional[str]:
        # Ensure Docker client is initialized
        if not self._ensure_client():  # Removed memory_gb from call
            self._logger.error(
                "Failed to initialize Docker client. Cannot start container."
            )
            return None

        self._remove_container_if_exists(name)

        try:
            self._logger.info(f"Attempting to run container '{name}'...")
            # If you need to set memory limits for the container itself, use mem_limit parameter:
            # e.g., mem_limit=f"{memory_gb}g" if memory_gb was for the container.
            # For now, assuming it was for Colima and thus removed.
            container = self._client.containers.run(
                name=name,
                image=image,
                network=network,
                volumes=volume_setup,
                ports=ports,
                environment=env_vars,
                detach=detach,
                remove=remove,
            )
            self._logger.info(
                f"Container {name}:{container.short_id} started successfully."
            )
            return container.id

        except APIError as api_err:
            self._logger.error(f"Docker API error starting container {name}: {api_err}")
            if "port is already allocated" in str(api_err):
                self._logger.error(
                    f"Port conflict: Check if ports {list(ports.values())} are already in use."
                )
            elif "container name" in str(api_err) and "is already in use" in str(
                api_err
            ):
                self._logger.error(
                    f"Container name conflict: Container '{name}' might still exist despite removal attempt."
                )
            return None
        except Exception as e:
            self._logger.error(
                f"Generic error starting container {name}: {e}", exc_info=True
            )
            return None

    def stop_container(self, name: str) -> bool:
        """Stops a running container by name."""
        if not self._ensure_client():
            return False

        try:
            self._logger.info(f"Attempting to stop container '{name}'...")
            container = self._client.containers.get(name)
            container.stop()
            self._logger.info(f"Container '{name}' stopped successfully.")
            return True
        except NotFound:
            self._logger.warning(f"Container '{name}' not found, cannot stop.")
            return False
        except APIError as api_err:
            self._logger.error(f"Docker API error stopping container {name}: {api_err}")
            return False
        except Exception as e:
            self._logger.error(
                f"Generic error stopping container {name}: {e}", exc_info=True
            )
            return False

    def remove_container(self, name: str) -> bool:
        """Removes a container by name (forcefully)."""
        if not self._ensure_client():
            return False

        try:
            self._logger.info(f"Attempting to remove container '{name}'...")
            container = self._client.containers.get(name)
            container.remove(force=True)
            self._logger.info(f"Container '{name}' removed successfully.")
            return True
        except NotFound:
            self._logger.warning(f"Container '{name}' not found, cannot remove.")
            return False
        except APIError as api_err:
            self._logger.error(f"Docker API error removing container {name}: {api_err}")
            return False
        except Exception as e:
            self._logger.error(
                f"Generic error removing container {name}: {e}", exc_info=True
            )
            return False

    def _remove_container_if_exists(self, container_name: str):
        """Stops and removes a container if it exists."""
        if not self._ensure_client():
            return

        try:
            container = self._client.containers.get(container_name)
            self._logger.info(
                f"Container '{container_name}' found. Stopping and removing..."
            )
            try:
                container.stop()
            except APIError as stop_err:
                self._logger.warning(
                    f"Error stopping container {container_name} before removal: {stop_err}"
                )
            container.remove(force=True)
            self._logger.info(f"Container '{container_name}' removed.")
        except NotFound:
            self._logger.info(
                f"Container '{container_name}' not found, no removal needed."
            )
        except APIError as api_err:
            self._logger.error(
                f"Docker API error trying to remove container {container_name}: {api_err}"
            )
        except Exception as e:
            self._logger.error(
                f"Generic error removing container {container_name}: {e}", exc_info=True
            )

    def get_container_status(self, name: str) -> str:
        """Gets the status of a container by name."""
        if not self._ensure_client():
            return "error (client init failed)"

        try:
            container = self._client.containers.get(name)
            return container.status
        except NotFound:
            return "not found"
        except APIError as api_err:
            self._logger.error(f"Docker API error getting status for {name}: {api_err}")
            return "error (api)"
        except Exception as e:
            self._logger.error(
                f"Generic error getting status for {name}: {e}", exc_info=True
            )
            return "error (general)"

    def _create_network(self, network_name: str):
        if not self._ensure_client():
            return
        try:
            self._client.networks.get(network_name)
            self._logger.info(f"Network '{network_name}' already exists.")
        except NotFound:
            self._logger.info(f"Network '{network_name}' not found. Creating...")
            try:
                self._client.networks.create(network_name, driver="bridge")
                self._logger.info(f"Network '{network_name}' created successfully.")
            except APIError as api_err:
                self._logger.error(
                    f"Docker API error creating network {network_name}: {api_err}"
                )
            except Exception as e:
                self._logger.error(
                    f"Error creating network {network_name}: {e}", exc_info=True
                )
        except APIError as api_err:
            self._logger.error(
                f"Docker API error checking network {network_name}: {api_err}"
            )
        except Exception as e:
            self._logger.error(
                f"Error checking network {network_name}: {e}", exc_info=True
            )

    def _create_volume(self, volume_name: str):
        if not self._ensure_client():
            return
        try:
            self._client.volumes.get(volume_name)
            self._logger.info(f"Volume '{volume_name}' already exists.")
        except NotFound:
            self._logger.info(f"Volume '{volume_name}' not found. Creating...")
            try:
                self._client.volumes.create(volume_name)
                self._logger.info(f"Volume '{volume_name}' created successfully.")
            except APIError as api_err:
                self._logger.error(
                    f"Docker API error creating volume {volume_name}: {api_err}"
                )
            except Exception as e:
                self._logger.error(
                    f"Error creating volume {volume_name}: {e}", exc_info=True
                )
        except APIError as api_err:
            self._logger.error(
                f"Docker API error checking volume {volume_name}: {api_err}"
            )
        except Exception as e:
            self._logger.error(
                f"Error checking volume {volume_name}: {e}", exc_info=True
            )

    def _pull_image(self, image: str) -> None:
        if not self._ensure_client():
            return
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

    def _start_daemon(self) -> Optional[docker.client.DockerClient]:
        """
        Attempts to connect to an existing Docker daemon.
        The user is responsible for ensuring the Docker daemon is running and accessible.
        """
        self._logger.info(
            "Attempting to connect to Docker daemon. Ensure it is running and accessible."
        )
        try:
            client = docker.from_env()
            client.ping()  # Test connection
            self._logger.info("Successfully connected to Docker daemon.")
            return client
        except Exception as e:
            self._logger.error(
                f"Failed to connect to Docker daemon: {e}. "
                "Please ensure Docker (e.g., Docker Desktop, Colima, or native Docker service) "
                "is running and configured correctly."
            )
            return None

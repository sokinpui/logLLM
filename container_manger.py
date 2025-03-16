from abc import ABC, abstractmethod

from logger import Logger
import config as cfg

import platform
import subprocess
import os
import docker

class ContainerManager(ABC):
    @abstractmethod
    def start_container(self):
        pass

    @abstractmethod
    def stop_container(self):
        pass

    @abstractmethod
    def get_container_status(self):
        pass

class DockerManager(ContainerManager):

    def __init__(self):
        self._logger = Logger()
        self._client = self._start_daemon()
        self.id = None

    def start_container(self,
                        name: str,
                        image: str,
                        network: str,
                        volume_setup: dict,
                        ports: dict,
                        env_vars: dict,
                        detach: bool,
                        remove: bool,
                        ): # -> container_id: str | None

        self._remove_container(name)

        try:
            container = self._client.containers.run(
                name=name,
                image=image,
                network=network,
                volumes=volume_setup,
                ports=ports,
                environment=env_vars,
                detach=detach,
                remove=remove
            )
            self._logger.info(f"Container {name}:{container.id} started successfully")

            return container.id

        except Exception as e:
            self._logger.error(f"Error starting container {name}: {e}")
            return None

    def stop_container(self):
        print(f"Stopping container using Docker")

    def get_container_status(self):
        print(f"Getting status of container using Docker")

    def _remove_container(self, container_name: str):
        try:
            container = self._client.containers.get(container_name)
            container.remove(force=True)
            self._logger.info(f"Container {container_name} removed successfully")
        except docker.errors.NotFound:
            self._logger.info(f"Container {container_name} not found")
        except Exception as e:
            self._logger.error(f"Error removing container {container_name}: {e}")

    def _create_network(self, network_name : str):
        try:
            self._client.networks.get(network_name)
            self._logger.info(f"Volume {network_name} already exists")
        except docker.errors.NotFound:
            self._logger.info(f"Volume {network_name} not found. Creating volume...")
            self._client.networks.create(network_name)
            self._logger.info(f"Volume {network_name} created successfully")
        except Exception as e:
            self._logger.error(f"Error creating volume {network_name}: {e}")

    def _create_volume(self, volume_name : str):
        try:
            self._client.volumes.get(volume_name)
            self._logger.info(f"Volume {volume_name} already exists")
        except docker.errors.NotFound:
            self._logger.info(f"Volume {volume_name} not found. Creating volume...")
            self._client.volumes.create(volume_name)
            self._logger.info(f"Volume {volume_name} created successfully")
        except Exception as e:
            self._logger.error(f"Error creating volume {volume_name}: {e}")

    def _pull_image(self, image : str) -> None:
        try:
            self._client.images.get(image)
            self._logger.info(f"Image {image} already exists")
        except docker.errors.NotFound:
            self._logger.info(f"Image {image} not found. Pulling image...")
            self._client.images.pull(image)
            self._logger.info(f"Image {image} pulled successfully")
        except Exception as e:
            self._logger.error(f"Error pulling image {image}: {e}")

    def _start_daemon(self): # -> docker.client.DockerClient:
        if platform.system() == "Windows":
            self._logger.error("Docker daemon is not supported on Windows")

        elif platform.system() == "Linux":
            self._logger.info("system running on Linux")

        elif platform.system() == "Darwin":
            self._logger.info("system running on MacOS")

            # use colima to start docker daemon
            try:
                colima_memory_size = str(cfg.COLIMA_MEMORY_SIZE)
                res = subprocess.run(["colima", "status"], capture_output=True, text=True)
                if 'level=fatal' in res.stderr:
                    # config make the memory configurable
                    subprocess.run(['colima', 'start', '--memory', colima_memory_size])
                    self._logger.info("Colima started successfully")
                else:
                    self._logger.info("Colima is already running")

                home_dir = os.getenv('HOME')
                os.environ['DOCKER_HOST'] = f'unix://{home_dir}/.colima/default/docker.sock'
                self._client = docker.from_env()
                return self._client

            except Exception as e:
                self._logger.error(f"Error starting colima: {e}")


def main():

    # Elastic Search
    elastic_manager = DockerManager()

    elastic_manager._start_daemon()

    elastic_search_image = cfg.ELASTIC_SEARCH_IMAGE
    elastic_search_network = cfg.DOCKER_NETWORK_NAME
    elastic_search_volume = cfg.DOCKER_VOLUME_SETUP
    elastic_search_volume_name = cfg.DOCKER_VOLUME_NAME
    elastic_search_ports = cfg.ELASTIC_SEARCH_PORTS
    elastic_search_env_vars = cfg.ELASTIC_SEARCH_ENVIRONMENT
    elastic_container_name = cfg.ELASTIC_SEARCH_CONTAINER_NAME

    elastic_manager._create_network(elastic_search_network)
    elastic_manager._create_volume(elastic_search_volume_name)
    elastic_manager._pull_image(elastic_search_image)

    elastic_manager.id = elastic_manager.start_container(
            name=elastic_container_name,
            image=elastic_search_image,
            network=elastic_search_network,
            volume_setup=elastic_search_volume,
            ports=elastic_search_ports,
            env_vars=elastic_search_env_vars,
            detach=cfg.DOCKER_DETACH,
            remove=cfg.DOCKER_REMOVE
    )

    # Kibana
    kibana_manager = DockerManager()

    kibana_image = cfg.KIBANA_IMAGE
    kiabana_network = cfg.DOCKER_NETWORK_NAME
    kibana_ports = cfg.KIBANA_PORTS
    kiabana_env_vars = cfg.KIBANA_ENVIRONMENT
    kibana_container_name = cfg.KIBANA_CONTAINER_NAME

    kibana_manager._pull_image(kibana_image)

    kibana_manager.id = kibana_manager.start_container(
            name=kibana_container_name,
            image=kibana_image,
            network=kiabana_network,
            volume_setup={},
            ports=kibana_ports,
            env_vars=kiabana_env_vars,
            detach=cfg.DOCKER_DETACH,
            remove=cfg.DOCKER_REMOVE
    )

if __name__ == "__main__":
    main()

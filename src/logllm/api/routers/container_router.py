import requests  # Added for service health checks
from fastapi import APIRouter, HTTPException

from ...config import config as cfg  # Adjust path if necessary

# --- UNCOMMENT AND IMPORT ACTUAL MANAGER AND CONFIG ---
from ...utils.container_manager import DockerManager  # Adjust path if necessary
from ..models.common_models import MessageResponse
from ..models.container_models import ContainerDetailItem  # Updated
from ..models.container_models import VolumeDetailItem  # Added
from ..models.container_models import (
    ContainerStatusResponse,
    ContainerStopRequest,
)

router = APIRouter()
# --- INSTANTIATE THE MANAGER ---
# This assumes DockerManager() can be instantiated safely here.
# If it needs specific setup or can fail, you might do this in a startup event
# or handle potential errors during instantiation.
try:
    manager = DockerManager()
except Exception as e:
    # If DockerManager fails to initialize (e.g., docker library not installed,
    # or some critical config missing for the manager itself),
    # we should handle it. For now, we'll let it raise if fatal.
    # A more robust approach might be to have a 'health check' for the manager.
    print(f"Error initializing DockerManager: {e}")
    # Depending on severity, you might raise an error or have a fallback.
    # For now, if it fails here, routes calling manager methods will fail.
    manager = None  # Or a mock manager if you want API to still "work" with errors


@router.post("/start", response_model=MessageResponse)
async def start_container_services():
    if not manager:
        raise HTTPException(status_code=503, detail="DockerManager not available.")
    try:
        # Ensure Docker client is available within the manager
        if not manager._ensure_client():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Docker daemon. Is it running?",
            )

        # You'd have more detailed logic here from your CLI start command
        manager._create_network(cfg.DOCKER_NETWORK_NAME)
        manager._create_volume(cfg.DOCKER_VOLUME_NAME)
        manager._pull_image(cfg.ELASTIC_SEARCH_IMAGE)
        manager._pull_image(cfg.KIBANA_IMAGE)

        es_id = manager.start_container(
            name=cfg.ELASTIC_SEARCH_CONTAINER_NAME,
            image=cfg.ELASTIC_SEARCH_IMAGE,
            network=cfg.DOCKER_NETWORK_NAME,
            volume_setup=cfg.DOCKER_VOLUME_SETUP,
            ports=cfg.ELASTIC_SEARCH_PORTS,
            env_vars=cfg.ELASTIC_SEARCH_ENVIRONMENT,
            detach=cfg.DOCKER_DETACH,
            remove=cfg.DOCKER_REMOVE,
        )
        kbn_id = manager.start_container(
            name=cfg.KIBANA_CONTAINER_NAME,
            image=cfg.KIBANA_IMAGE,
            network=cfg.DOCKER_NETWORK_NAME,
            volume_setup={},
            ports=cfg.KIBANA_PORTS,
            env_vars=cfg.KIBANA_ENVIRONMENT,
            detach=cfg.DOCKER_DETACH,
            remove=cfg.DOCKER_REMOVE,
        )
        if es_id and kbn_id:
            return MessageResponse(
                message="Elasticsearch and Kibana containers starting."
            )
        elif es_id:
            return MessageResponse(
                message="Elasticsearch started, Kibana failed. Check logs."
            )
        elif kbn_id:
            return MessageResponse(
                message="Kibana started, Elasticsearch failed. Check logs."
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to start one or more containers."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error starting containers: {str(e)}"
        )
    # return MessageResponse(message="Containers start process initiated (mock).") # Remove mock


@router.post("/stop", response_model=MessageResponse)
async def stop_container_services(request: ContainerStopRequest):
    if not manager:
        raise HTTPException(status_code=503, detail="DockerManager not available.")
    try:
        if not manager._ensure_client():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Docker daemon. Is it running?",
            )

        es_stopped = manager.stop_container(cfg.ELASTIC_SEARCH_CONTAINER_NAME)
        kbn_stopped = manager.stop_container(cfg.KIBANA_CONTAINER_NAME)

        message = []
        if es_stopped:
            message.append(f"{cfg.ELASTIC_SEARCH_CONTAINER_NAME} stopped.")
        else:
            message.append(
                f"{cfg.ELASTIC_SEARCH_CONTAINER_NAME} not found or failed to stop."
            )
        if kbn_stopped:
            message.append(f"{cfg.KIBANA_CONTAINER_NAME} stopped.")
        else:
            message.append(f"{cfg.KIBANA_CONTAINER_NAME} not found or failed to stop.")

        if request.remove:
            es_removed = manager.remove_container(cfg.ELASTIC_SEARCH_CONTAINER_NAME)
            kbn_removed = manager.remove_container(cfg.KIBANA_CONTAINER_NAME)
            if es_removed:
                message.append(f"{cfg.ELASTIC_SEARCH_CONTAINER_NAME} removed.")
            if kbn_removed:
                message.append(f"{cfg.KIBANA_CONTAINER_NAME} removed.")

            # Optionally remove volume if requested and no containers are using it
            # For now, volume removal is not part of this endpoint to prevent accidental data loss.
            # It could be a separate explicit action.

            return MessageResponse(message=" ".join(message))
        return MessageResponse(message=" ".join(message))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error stopping containers: {str(e)}"
        )
    # return MessageResponse( # Remove mock
    #     message=f"Containers stopped (remove: {request.remove}) (mock)."
    # )


@router.get("/status", response_model=ContainerStatusResponse)
async def get_container_services_status():
    container_details_list = []
    volume_details = None

    if not manager:
        # Manager initialization failed
        es_item = ContainerDetailItem(
            name=cfg.ELASTIC_SEARCH_CONTAINER_NAME, status="error (manager init failed)"
        )
        kbn_item = ContainerDetailItem(
            name=cfg.KIBANA_CONTAINER_NAME, status="error (manager init failed)"
        )
        container_details_list.extend([es_item, kbn_item])
        volume_details = VolumeDetailItem(
            name=cfg.DOCKER_VOLUME_NAME, status="error (manager init failed)"
        )
        return ContainerStatusResponse(
            statuses=container_details_list, volume_info=volume_details
        )

    try:
        manager._ensure_client()  # Try to connect, but get_container_details handles individual failures

        es_details_dict = manager.get_container_details(
            cfg.ELASTIC_SEARCH_CONTAINER_NAME
        )
        kbn_details_dict = manager.get_container_details(cfg.KIBANA_CONTAINER_NAME)

        es_item = ContainerDetailItem(**es_details_dict)
        kbn_item = ContainerDetailItem(**kbn_details_dict)

        # --- Service Health Checks ---
        # Elasticsearch
        if (
            es_item.status and "up" in es_item.status.lower()
        ):  # Check if container is running
            es_host_port = cfg.ELASTIC_SEARCH_PORTS.get("9200/tcp")
            if es_host_port:
                es_item.service_url = f"http://localhost:{es_host_port}"
                try:
                    # Use a timeout for requests
                    response = requests.get(
                        f"{es_item.service_url}/_cluster/health", timeout=2
                    )
                    if response.status_code == 200:
                        cluster_health = response.json()
                        es_item.service_status = cluster_health.get(
                            "status", "Unknown"
                        ).capitalize()  # e.g. Green, Yellow, Red
                    else:
                        es_item.service_status = f"API Error ({response.status_code})"
                except requests.exceptions.ConnectionError:
                    es_item.service_status = "Unreachable"
                except requests.exceptions.Timeout:
                    es_item.service_status = "Timeout"
                except Exception:
                    es_item.service_status = "Check Error"  # Generic error
            else:
                es_item.service_status = "Port N/A"
        elif es_item.status != "not found":
            es_item.service_status = "Container Not Running"
        else:  # 'not found'
            es_item.service_status = "N/A"

        # Kibana
        if (
            kbn_item.status and "up" in kbn_item.status.lower()
        ):  # Check if container is running
            kbn_host_port = cfg.KIBANA_PORTS.get("5601/tcp")
            if kbn_host_port:
                kbn_item.service_url = f"http://localhost:{kbn_host_port}"
                try:
                    response = requests.get(
                        f"{kbn_item.service_url}/api/status", timeout=3
                    )
                    if response.status_code == 200:
                        kibana_status_data = response.json()
                        overall_status = (
                            kibana_status_data.get("status", {})
                            .get("overall", {})
                            .get("state", "Unknown")
                        )
                        kbn_item.service_status = (
                            overall_status.capitalize()
                        )  # e.g. Available, Critical
                    else:
                        kbn_item.service_status = f"API Error ({response.status_code})"
                except requests.exceptions.ConnectionError:
                    kbn_item.service_status = "Unreachable"
                except requests.exceptions.Timeout:
                    kbn_item.service_status = "Timeout"
                except Exception:
                    kbn_item.service_status = "Check Error"  # Generic error
            else:
                kbn_item.service_status = "Port N/A"
        elif kbn_item.status != "not found":
            kbn_item.service_status = "Container Not Running"
        else:  # 'not found'
            kbn_item.service_status = "N/A"
        # --- End Service Health Checks ---

        container_details_list.extend([es_item, kbn_item])

        # Get volume details
        volume_dict = manager.get_volume_details(cfg.DOCKER_VOLUME_NAME)
        volume_details = VolumeDetailItem(**volume_dict)

        return ContainerStatusResponse(
            statuses=container_details_list, volume_info=volume_details
        )

    except Exception as e:
        # This catch-all is for unexpected errors during status check
        es_item_err = ContainerDetailItem(
            name=cfg.ELASTIC_SEARCH_CONTAINER_NAME,
            status=f"error ({str(e)})",
            service_status="Error",
        )
        kbn_item_err = ContainerDetailItem(
            name=cfg.KIBANA_CONTAINER_NAME,
            status=f"error ({str(e)})",
            service_status="Error",
        )
        container_details_list.extend([es_item_err, kbn_item_err])
        volume_details_err = VolumeDetailItem(
            name=cfg.DOCKER_VOLUME_NAME, status=f"error ({str(e)})"
        )
        return ContainerStatusResponse(
            statuses=container_details_list, volume_info=volume_details_err
        )


@router.post("/restart", response_model=MessageResponse)
async def restart_container_services():
    if not manager:
        raise HTTPException(status_code=503, detail="DockerManager not available.")
    try:
        if not manager._ensure_client():
            raise HTTPException(
                status_code=503,
                detail="Cannot connect to Docker daemon. Is it running?",
            )
        # Stop
        await stop_container_services(
            ContainerStopRequest(remove=False)
        )  # Call existing stop logic
        # Start
        # Wait a bit for containers to fully stop
        import asyncio

        await asyncio.sleep(5)  # Non-blocking sleep
        start_response = await start_container_services()  # Call existing start logic
        return MessageResponse(
            message=f"Restart process initiated. {start_response.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error restarting containers: {str(e)}"
        )
    # return MessageResponse(message="Containers restart process initiated (mock).") # Remove mock

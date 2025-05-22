from fastapi import APIRouter, HTTPException

from ...config import config as cfg  # Adjust path if necessary

# --- UNCOMMENT AND IMPORT ACTUAL MANAGER AND CONFIG ---
from ...utils.container_manager import DockerManager  # Adjust path if necessary
from ..models.common_models import MessageResponse
from ..models.container_models import (
    ContainerStatusItem,
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
    if not manager:
        # If manager didn't initialize, return an error status for all
        return ContainerStatusResponse(
            statuses=[
                ContainerStatusItem(
                    name=cfg.ELASTIC_SEARCH_CONTAINER_NAME,
                    status="error (manager init failed)",
                ),
                ContainerStatusItem(
                    name=cfg.KIBANA_CONTAINER_NAME, status="error (manager init failed)"
                ),
            ]
        )
    try:
        # --- UNCOMMENT THE REAL LOGIC ---
        # Ensure Docker client is available within the manager
        # It's okay for _ensure_client to return False if Docker isn't running.
        # get_container_status should then return "error" or "not found".
        manager._ensure_client()  # Try to connect, but don't fail hard if it doesn't.

        es_status = manager.get_container_status(cfg.ELASTIC_SEARCH_CONTAINER_NAME)
        kbn_status = manager.get_container_status(cfg.KIBANA_CONTAINER_NAME)
        return ContainerStatusResponse(
            statuses=[
                ContainerStatusItem(
                    name=cfg.ELASTIC_SEARCH_CONTAINER_NAME, status=es_status
                ),
                ContainerStatusItem(name=cfg.KIBANA_CONTAINER_NAME, status=kbn_status),
            ]
        )
    except Exception as e:
        # This catch-all is for unexpected errors during status check
        # Individual container errors (like "not found") are handled by get_container_status
        # and returned as part of the status string.
        return ContainerStatusResponse(
            statuses=[
                ContainerStatusItem(
                    name=cfg.ELASTIC_SEARCH_CONTAINER_NAME, status=f"error ({str(e)})"
                ),
                ContainerStatusItem(
                    name=cfg.KIBANA_CONTAINER_NAME, status=f"error ({str(e)})"
                ),
            ]
        )
    # --- REMOVE THE MOCK RESPONSE ---
    # mock_statuses = [
    #     ContainerStatusItem(name="movelook_elastic_search", status="running (mock)"),
    #     ContainerStatusItem(name="movelook_kibana", status="stopped (mock)"),
    # ]
    # return ContainerStatusResponse(statuses=mock_statuses)


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

# src/logllm/cli/container.py
import argparse
import time

from logllm.config import config as cfg

# Use absolute imports
from logllm.utils.container_manager import DockerManager
from logllm.utils.logger import Logger

# import subprocess # No longer needed for Colima stop


logger = Logger()


# --- Handler for 'start' ---
def handle_container_start(args):
    # logger.info(f"Executing container start... Requested memory: {args.memory}GB") # Memory arg removed
    logger.info(f"Executing container start...")
    manager = DockerManager()

    logger.info("Initializing Docker client and checking daemon status...")
    if not manager._ensure_client():  # memory_gb argument removed
        print(
            "ERROR: Failed to initialize Docker client. Please ensure Docker daemon is running. Aborting start."
        )
        logger.error(
            "Aborting container start due to Docker client initialization failure."
        )
        return
    logger.info("Docker client initialized successfully.")

    # --- Start Elasticsearch ---
    logger.info("--- Starting Elasticsearch Container ---")
    elastic_search_image = cfg.ELASTIC_SEARCH_IMAGE
    elastic_search_network = cfg.DOCKER_NETWORK_NAME
    elastic_search_volume = cfg.DOCKER_VOLUME_SETUP
    elastic_search_volume_name = cfg.DOCKER_VOLUME_NAME
    elastic_search_ports = cfg.ELASTIC_SEARCH_PORTS
    elastic_search_env_vars = cfg.ELASTIC_SEARCH_ENVIRONMENT
    elastic_container_name = cfg.ELASTIC_SEARCH_CONTAINER_NAME

    logger.info("Ensuring Docker network exists...")
    manager._create_network(elastic_search_network)
    logger.info("Ensuring Docker volume exists...")
    manager._create_volume(elastic_search_volume_name)
    logger.info("Ensuring Elasticsearch image exists...")
    manager._pull_image(elastic_search_image)

    logger.info(f"Starting container {elastic_container_name}...")
    es_id = manager.start_container(
        name=elastic_container_name,
        image=elastic_search_image,
        network=elastic_search_network,
        volume_setup=elastic_search_volume,
        ports=elastic_search_ports,
        env_vars=elastic_search_env_vars,
        detach=cfg.DOCKER_DETACH,
        remove=cfg.DOCKER_REMOVE,
        # memory_gb=args.memory, # Removed
    )
    if es_id:
        print(
            f"Elasticsearch container '{elastic_container_name}' starting (ID: {es_id[:12]})..."
        )
    else:
        print(
            f"ERROR: Failed to start Elasticsearch container '{elastic_container_name}'. Check logs."
        )

    # --- Start Kibana ---
    logger.info("--- Starting Kibana Container ---")
    kibana_image = cfg.KIBANA_IMAGE
    kibana_network = cfg.DOCKER_NETWORK_NAME
    kibana_ports = cfg.KIBANA_PORTS
    kibana_env_vars = cfg.KIBANA_ENVIRONMENT
    kibana_container_name = cfg.KIBANA_CONTAINER_NAME

    logger.info("Ensuring Kibana image exists...")
    manager._pull_image(kibana_image)

    logger.info(f"Starting container {kibana_container_name}...")
    kbn_id = manager.start_container(
        name=kibana_container_name,
        image=kibana_image,
        network=kibana_network,
        volume_setup={},  # Kibana usually doesn't need a persistent volume like ES
        ports=kibana_ports,
        env_vars=kibana_env_vars,
        detach=cfg.DOCKER_DETACH,
        remove=cfg.DOCKER_REMOVE,
    )
    if kbn_id:
        print(
            f"Kibana container '{kibana_container_name}' starting (ID: {kbn_id[:12]})..."
        )
    else:
        print(
            f"ERROR: Failed to start Kibana container '{kibana_container_name}'. Check logs."
        )

    logger.info("Container start command finished.")
    print("\nContainer start process initiated. Use 'status' command to check.")


# --- handle_container_stop ---
def handle_container_stop(args):
    # logger.info(f"Executing container stop... Remove: {args.remove}, Stop Colima: {args.stop_colima}") # Stop Colima removed
    logger.info(f"Executing container stop... Remove: {args.remove}")
    manager = DockerManager()
    es_name = cfg.ELASTIC_SEARCH_CONTAINER_NAME
    kbn_name = cfg.KIBANA_CONTAINER_NAME

    print(f"Stopping container '{kbn_name}'...")
    kbn_stopped = manager.stop_container(kbn_name)
    print(f"Stopping container '{es_name}'...")
    es_stopped = manager.stop_container(es_name)

    if args.remove:
        print("---")
        print(f"Removing container '{kbn_name}'...")
        kbn_removed = manager.remove_container(
            kbn_name
        )  # kbn_removed not used, but fine
        print(f"Removing container '{es_name}'...")
        es_removed = manager.remove_container(es_name)  # es_removed not used, but fine

    if args.remove:
        print("\nStop and Remove process finished.")
    else:
        print("\nStop process finished.")
    logger.info(
        f"Container stop finished. ES Stopped: {es_stopped}, KBN Stopped: {kbn_stopped}"
    )


# --- handle_container_status (Remains the same) ---
def handle_container_status(args):
    logger.info("Executing container status...")
    manager = DockerManager()
    es_name = cfg.ELASTIC_SEARCH_CONTAINER_NAME
    kbn_name = cfg.KIBANA_CONTAINER_NAME

    print("Checking container status...")
    es_status = manager.get_container_status(es_name)
    kbn_status = manager.get_container_status(kbn_name)

    print(f"  - {es_name:<30}: {es_status}")
    print(f"  - {kbn_name:<30}: {kbn_status}")
    logger.info(f"Container status check complete. ES: {es_status}, KBN: {kbn_status}")


# --- handle_container_restart ---
def handle_container_restart(args):
    # logger.info(f"Executing container restart... Requested memory: {args.memory}GB") # Memory arg removed
    logger.info(f"Executing container restart...")
    print("--- Restarting Containers ---")

    stop_args = argparse.Namespace(
        remove=False  # Stop Colima option removed from Namespace
    )
    handle_container_stop(stop_args)

    print("Waiting a few seconds before starting...")
    time.sleep(5)

    # start_args = argparse.Namespace(memory=args.memory) # Memory arg removed
    start_args = (
        argparse.Namespace()
    )  # No specific args needed for start from restart context now
    handle_container_start(start_args)

    print("\n--- Restart process finished ---")
    logger.info("Container restart finished.")


# --- Register Parser Function ---
def register_container_parser(subparsers):
    container_parser = subparsers.add_parser(
        "db",
        help="Manage database engine in Docker containers (Elasticsearch, Kibana). User must ensure Docker daemon is running.",
        description="Start, stop, restart, or check the status of the necessary Docker containers. Assumes Docker daemon is already running and accessible.",
    )
    container_subparsers = container_parser.add_subparsers(
        dest="container_action", help="Container actions", required=True
    )

    # Start command
    start_parser = container_subparsers.add_parser(
        "start",
        help="Start Elasticsearch and Kibana containers. Requires Docker daemon to be running.",
    )
    start_parser.set_defaults(func=handle_container_start)

    # Stop command
    stop_parser = container_subparsers.add_parser(
        "stop", help="Stop Elasticsearch and Kibana containers"
    )
    stop_parser.add_argument(
        "--remove",
        action="store_true",
        help="Also remove the containers after stopping them.",
    )
    stop_parser.set_defaults(func=handle_container_stop)

    # Status command
    status_parser = container_subparsers.add_parser(
        "status", help="Check current status of containers"
    )
    status_parser.set_defaults(func=handle_container_status)

    # Restart command
    restart_parser = container_subparsers.add_parser(
        "restart",
        help="Stop and then start containers. Requires Docker daemon to be running.",
    )
    restart_parser.set_defaults(func=handle_container_restart)

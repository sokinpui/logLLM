# src/logllm/cli/container.py
import argparse
import time
import subprocess # Ensure subprocess is imported

# Use absolute imports
from logllm.utils.container_manager import DockerManager
from logllm.config import config as cfg
from logllm.utils.logger import Logger

logger = Logger()

# --- Handler for 'start' ---
def handle_container_start(args):
    logger.info(f"Executing container start... Requested memory: {args.memory}GB")
    manager = DockerManager()

    # --- STEP 1: Explicitly ensure client and start daemon if needed ---
    # Call _ensure_client FIRST, passing the memory argument.
    # This guarantees that if Colima needs starting, it uses the CLI value.
    logger.info("Initializing Docker client and checking daemon status...")
    if not manager._ensure_client(memory_gb=args.memory):
        print("ERROR: Failed to initialize Docker client or start daemon. Aborting start.")
        logger.error("Aborting container start due to Docker client initialization failure.")
        return
    logger.info("Docker client initialized successfully.")
    # --- END STEP 1 ---

    # --- Start Elasticsearch ---
    logger.info("--- Starting Elasticsearch Container ---")
    elastic_search_image = cfg.ELASTIC_SEARCH_IMAGE
    elastic_search_network = cfg.DOCKER_NETWORK_NAME
    elastic_search_volume = cfg.DOCKER_VOLUME_SETUP
    elastic_search_volume_name = cfg.DOCKER_VOLUME_NAME
    elastic_search_ports = cfg.ELASTIC_SEARCH_PORTS
    elastic_search_env_vars = cfg.ELASTIC_SEARCH_ENVIRONMENT
    elastic_container_name = cfg.ELASTIC_SEARCH_CONTAINER_NAME

    # These calls will now use the already initialized client.
    logger.info("Ensuring Docker network exists...")
    manager._create_network(elastic_search_network)
    logger.info("Ensuring Docker volume exists...")
    manager._create_volume(elastic_search_volume_name)
    logger.info("Ensuring Elasticsearch image exists...")
    manager._pull_image(elastic_search_image)

    logger.info(f"Starting container {elastic_container_name}...")
    # We still pass memory_gb here, although it won't re-trigger daemon start,
    # it's harmless and keeps the signature consistent if start_container
    # itself ever needed the value directly.
    es_id = manager.start_container(
            name=elastic_container_name,
            image=elastic_search_image,
            network=elastic_search_network,
            volume_setup=elastic_search_volume,
            ports=elastic_search_ports,
            env_vars=elastic_search_env_vars,
            detach=cfg.DOCKER_DETACH,
            remove=cfg.DOCKER_REMOVE,
            memory_gb=args.memory # Pass memory argument
    )
    if es_id:
        print(f"Elasticsearch container '{elastic_container_name}' starting (ID: {es_id[:12]})...")
    else:
        print(f"ERROR: Failed to start Elasticsearch container '{elastic_container_name}'. Check logs.")

    # --- Start Kibana ---
    logger.info("--- Starting Kibana Container ---")
    kibana_image = cfg.KIBANA_IMAGE
    kibana_network = cfg.DOCKER_NETWORK_NAME
    kibana_ports = cfg.KIBANA_PORTS
    kibana_env_vars = cfg.KIBANA_ENVIRONMENT
    kibana_container_name = cfg.KIBANA_CONTAINER_NAME

    # Uses existing client
    logger.info("Ensuring Kibana image exists...")
    manager._pull_image(kibana_image)

    logger.info(f"Starting container {kibana_container_name}...")
    # No need to pass memory_gb here as daemon is already handled
    kbn_id = manager.start_container(
            name=kibana_container_name,
            image=kibana_image,
            network=kibana_network,
            volume_setup={},
            ports=kibana_ports,
            env_vars=kibana_env_vars,
            detach=cfg.DOCKER_DETACH,
            remove=cfg.DOCKER_REMOVE
            # memory_gb not needed here
    )
    if kbn_id:
        print(f"Kibana container '{kibana_container_name}' starting (ID: {kbn_id[:12]})...")
    else:
        print(f"ERROR: Failed to start Kibana container '{kibana_container_name}'. Check logs.")

    logger.info("Container start command finished.")
    print("\nContainer start process initiated. Use 'status' command to check.")

# --- handle_container_stop (Modified as per previous answer) ---
def handle_container_stop(args):
    logger.info(f"Executing container stop... Remove: {args.remove}, Stop Colima: {args.stop_colima}")
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
        kbn_removed = manager.remove_container(kbn_name)
        print(f"Removing container '{es_name}'...")
        es_removed = manager.remove_container(es_name)

    if args.stop_colima:
        print("---")
        print("Stopping Colima VM...")
        logger.info("Attempting to stop Colima VM...")
        try:
            status_res = subprocess.run(["colima", "status"], capture_output=True, text=True, check=False)
            if 'Running' in status_res.stdout:
                stop_res = subprocess.run(["colima", "stop"], check=True, capture_output=True, text=True)
                print("Colima VM stopped successfully.")
                logger.info("Colima VM stopped successfully.")
                logger.debug(f"Colima stop output:\n{stop_res.stdout}\n{stop_res.stderr}")
            else:
                print("Colima VM is already stopped.")
                logger.info("Colima VM was not running.")
        except FileNotFoundError:
            print("Error: 'colima' command not found. Cannot stop Colima.")
            logger.error("Colima command not found during stop.")
        except subprocess.CalledProcessError as cpe:
             print(f"Error stopping Colima VM: {cpe}")
             logger.error(f"Error executing colima stop: {cpe}\nstderr:\n{cpe.stderr}")
        except Exception as e:
             print(f"An unexpected error occurred while stopping Colima: {e}")
             logger.error(f"Unexpected error stopping Colima: {e}", exc_info=True)

    if args.remove:
        print("\nStop, Remove (and potentially Colima Stop) process finished.")
    else:
        print("\nStop (and potentially Colima Stop) process finished.")
    logger.info(f"Container stop finished. ES Stopped: {es_stopped}, KBN Stopped: {kbn_stopped}")


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

# --- handle_container_restart (Modified to ensure correct memory passing) ---
def handle_container_restart(args):
    logger.info(f"Executing container restart... Requested memory: {args.memory}GB")
    print("--- Restarting Containers ---")

    # 1. Stop Containers (pass stop-colima based on args? Or always keep colima running on restart?)
    # Let's assume restart keeps Colima running unless explicitly stopped separately.
    stop_args = argparse.Namespace(remove=False, stop_colima=False) # Don't stop colima during restart by default
    handle_container_stop(stop_args)

    # Optional: Wait a moment
    print("Waiting a few seconds before starting...")
    time.sleep(5)

    # 2. Start Containers (pass memory from restart args)
    # The explicit _ensure_client call in handle_container_start will now correctly
    # use the memory value if Colima had been stopped previously.
    start_args = argparse.Namespace(memory=args.memory)
    handle_container_start(start_args)

    print("\n--- Restart process finished ---")
    logger.info("Container restart finished.")


# --- Register Parser Function (Modified as per previous answer with --stop-colima) ---
def register_container_parser(subparsers):
    container_parser = subparsers.add_parser(
        'db',
        help='Manage database engine in Docker containers (Elasticsearch, Kibana) via Colima(MacOS)/Docker(Linux) daemon',
        description='Start, stop, restart, or check the status of the necessary Docker containers.'
        )
    container_subparsers = container_parser.add_subparsers(
        dest='container_action', help='Container actions', required=True
        )

    # Start command
    start_parser = container_subparsers.add_parser('start', help='Start Elasticsearch and Kibana containers')
    start_parser.add_argument(
        '-m', '--memory', type=int, default=cfg.COLIMA_MEMORY_SIZE,
        help=f'Memory (GB) for Colima VM if starting (default: {cfg.COLIMA_MEMORY_SIZE}GB).'
        )
    start_parser.set_defaults(func=handle_container_start)

    # Stop command
    stop_parser = container_subparsers.add_parser('stop', help='Stop Elasticsearch and Kibana containers')
    stop_parser.add_argument(
        '--remove', action='store_true', help='Also remove the containers after stopping them.'
        )
    stop_parser.add_argument( # Added flag
        '--stop-colima', action='store_true',
        help='Also stop the Colima virtual machine after stopping containers.'
        )
    stop_parser.set_defaults(func=handle_container_stop)

    # Status command
    status_parser = container_subparsers.add_parser('status', help='Check current status of containers')
    status_parser.set_defaults(func=handle_container_status)

    # Restart command
    restart_parser = container_subparsers.add_parser('restart', help='Stop and then start containers')
    restart_parser.add_argument(
        '-m', '--memory', type=int, default=cfg.COLIMA_MEMORY_SIZE,
        help=f'Memory (GB) for Colima VM if it needs starting during restart (default: {cfg.COLIMA_MEMORY_SIZE}GB).'
        )
    restart_parser.set_defaults(func=handle_container_restart)

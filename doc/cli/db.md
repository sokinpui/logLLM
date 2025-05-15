# logLLM CLI: `db` Command

The `db` command is used to manage the Docker containers for Elasticsearch and Kibana, which are essential backend services for storing and visualizing log data within `logLLM`. These commands typically interact with your local Docker daemon (or Colima on macOS).

**Base command:** `python -m src.logllm db <action> [OPTIONS]`

See also: [Global Options](./global_options.md)

---

## Actions

### `db start`

Starts the Elasticsearch and Kibana Docker containers.

- If running on macOS and Colima (a Docker Desktop alternative) is not active, this command will attempt to start Colima first.
- It ensures the necessary Docker network and volume are created.
- It pulls the required Elasticsearch and Kibana images if they are not present locally.

**Usage:**

```bash
python -m src.logllm db start [OPTIONS]
```

**Options:**

- `-m GB`, `--memory GB`:
  (Primarily for macOS/Colima) Specifies the memory (in Gigabytes) to allocate to the Colima virtual machine if it needs to be started. Defaults to the value configured in `src/logllm/config/config.py` (e.g., 4GB).

**Examples:**

```bash
# Start containers using default memory for Colima (if needed)
python -m src.logllm db start

# Start containers and allocate 6GB to Colima if it's not already running
python -m src.logllm db start -m 6
```

Upon successful execution, Elasticsearch will typically be accessible at `http://localhost:9200` and Kibana at `http://localhost:5601`.

---

### `db status`

Checks and displays the current operational status (e.g., 'running', 'exited', 'not found') of the `logLLM`-managed Elasticsearch and Kibana containers.

**Usage:**

```bash
python -m src.logllm db status
```

**Example Output:**

```
Checking container status...
  - movelook_elastic_search   : running
  - movelook_kibana           : running
```

If a container is not found or has exited, the status will reflect that.

---

### `db stop`

Stops the running Elasticsearch and Kibana containers. This does not remove the containers or their data by default, allowing them to be restarted later.

**Usage:**

```bash
python -m src.logllm db stop [OPTIONS]
```

**Options:**

- `--remove`:
  If specified, the containers will be permanently removed after they are stopped. This will delete any data stored within the containers unless it's on a persistent Docker volume (which `logLLM` configures for Elasticsearch data).
- `--stop-colima`:
  (macOS only) If specified, the Colima virtual machine will also be stopped after the `logLLM` containers are stopped. This effectively shuts down the Docker environment provided by Colima.

**Examples:**

```bash
# Stop the Elasticsearch and Kibana containers
python -m src.logllm db stop

# Stop and then remove the containers
python -m src.logllm db stop --remove

# Stop containers and also stop the Colima VM (macOS specific)
python -m src.logllm db stop --stop-colima
```

---

### `db restart`

A convenience command that stops and then immediately starts the Elasticsearch and Kibana containers. This is equivalent to running `db stop` followed by `db start`.

**Usage:**

```bash
python -m src.logllm db restart [OPTIONS]
```

**Options:**

- `-m GB`, `--memory GB`:
  Same as for `db start`. Specifies memory for Colima if it needs to be (re)started as part of the restart process.

**Example:**

```bash
# Restart containers, ensuring Colima (if it was stopped and needs restarting) gets 4GB
python -m src.logllm db restart -m 4
```

This is useful for applying configuration changes that require a service restart or for refreshing the container state.

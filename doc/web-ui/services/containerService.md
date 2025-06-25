# Container Service (`containerService.ts`)

## File: `frontend/src/services/containerService.ts`

### Overview

The `containerService.ts` module provides functions for interacting with the backend API endpoints related to Docker container management for `logLLM`'s backend services (Elasticsearch and Kibana). It uses the base `apiClient` for making HTTP requests.

### API Endpoint Prefix

- `const API_ENDPOINT = "/container";`

### Exported Functions

1.  **`getContainerStatus(): Promise<ContainerStatusResponse>`**

    - **Purpose**: Fetches the current status of the Elasticsearch and Kibana containers, as well as volume information.
    - **Method**: `GET`
    - **Endpoint**: `${API_ENDPOINT}/status`
    - **Response Type**: `ContainerStatusResponse` (defined in `frontend/src/types/api.ts`)
      - Contains an array of `ContainerDetailItem` for each service and optional `VolumeDetailItem`.

2.  **`startContainers(): Promise<MessageResponse>`**

    - **Purpose**: Sends a request to the backend to start the Elasticsearch and Kibana containers.
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/start`
    - **Response Type**: `MessageResponse` (typically `{ message: "Containers starting..." }`)

3.  **`stopContainers(params: ContainerStopRequest): Promise<MessageResponse>`**

    - **Purpose**: Sends a request to stop the containers.
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/stop`
    - **Request Body**: `params` (of type `ContainerStopRequest`, e.g., `{ remove: boolean }`) is stringified and sent.
    - **Response Type**: `MessageResponse`

4.  **`restartContainers(): Promise<MessageResponse>`**
    - **Purpose**: Sends a request to restart the containers (effectively a stop then start).
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/restart`
    - **Response Type**: `MessageResponse`

### Usage Example (from `ContainerPage.tsx`)

```typescript
// In ContainerPage.tsx
import * as containerService from "../services/containerService";

// To fetch status
const data = await containerService.getContainerStatus();
setContainerDetails(data.statuses);
setVolumeInfo(data.volume_info);

// To start containers
const response = await containerService.startContainers();
setSuccessMessage(response.message);

// To stop containers (optionally removing them)
const stopParams = { remove: removeOnStop }; // removeOnStop is a boolean state
const response = await containerService.stopContainers(stopParams);
setSuccessMessage(response.message);
```

This service abstracts the API call details, making the page components cleaner and focused on UI logic.

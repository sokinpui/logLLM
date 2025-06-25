# Container Management Page (`ContainerPage.tsx`)

## File: `frontend/src/pages/ContainerPage.tsx`

### Overview

The `ContainerPage` provides a user interface for managing the Docker containers that run the backend services for `logLLM`, primarily Elasticsearch and Kibana. Users can view the status of these services, start, stop, and restart them.

### Key Features

- **Status Display**:
  - Fetches and displays the status of configured containers (Elasticsearch, Kibana) and the associated Docker volume.
  - Shows container ID, port mappings, mounts, and crucially, the _service status_ (e.g., "Green", "Yellow", "Red" for Elasticsearch; "Available" for Kibana) by making HTTP requests to the services themselves if the container is running.
  - Provides a direct link to open Kibana if it's running and available.
- **Actions**:
  - **Start Services**: Initiates the startup of Elasticsearch and Kibana containers via an API call.
  - **Stop Services**: Stops the containers. Includes an option (`removeOnStop` switch) to also remove the containers after stopping.
  - **Restart Services**: Stops and then starts the containers.
- **Feedback**: Displays loading indicators during actions, and success or error messages using `Alert` components.
- **State Persistence**: The `removeOnStop` preference is saved to and loaded from local storage.

### State Management

- `containerDetails` (Array<ContainerDetailItem>): Stores detailed information about each container.
- `volumeInfo` (VolumeDetailItem | null): Stores details about the Docker volume.
- `loadingStatus` (boolean): Indicates if the initial status fetch is in progress.
- `actionLoading` (object): Tracks loading state for start, stop, and restart actions (e.g., `actionLoading.start`).
- `error` (string | null): Stores error messages to display to the user.
- `successMessage` (string | null): Stores success messages.
- `removeOnStop` (boolean): Controls whether containers are removed when stopped.

### Core Logic and Event Handlers

- **`fetchStatus(showLoadingSpinner: boolean)`**:
  - An asynchronous function (wrapped in `useCallback`) to fetch container and volume status from the backend using `containerService.getContainerStatus()`.
  - Updates `containerDetails`, `volumeInfo`, and `error` states.
  - Called on component mount and after actions.
- **`handleAction(action: Function, actionName: string, successMsgPrefix: string)`**:
  - A generic helper function to manage the lifecycle of start, stop, and restart actions.
  - Sets loading states, calls the provided `action` function (which is a service call), updates success/error messages, and triggers a status refresh.
- **`handleStart()`, `handleStop()`, `handleRestart()`**:
  - Specific handlers for the action buttons. They call `handleAction` with the appropriate service function from `containerService`.
  - `handleStop` passes the current `removeOnStop` state to the service.
- **Local Storage**: `useEffect` hooks are used to persist and retrieve the `removeOnStop` state.

### UI Elements

- **Main Paper Container**: Wraps the entire page content.
- **Title**: "Services Management".
- **Refresh Button**: Allows manual refreshing of service statuses.
- **Status Cards**:
  - One `Card` per container (Elasticsearch, Kibana) and one for the Volume.
  - Displays formatted name, container status (with color-coded chip), ID, ports, mounts.
  - **Service Status**: For containers, it additionally shows the health/status of the service running inside (e.g., Elasticsearch cluster health, Kibana API status) with a color-coded chip.
  - **Kibana Link**: A button to open Kibana in a new tab appears if Kibana is available.
- **Action Buttons**: "Start Services", "Stop Services", "Restart Services". These buttons are disabled during API calls or initial status loading.
- **"Remove on stop" Switch**: Allows users to toggle whether containers should be removed when the "Stop Services" action is performed.
- **Alerts**: For displaying success and error messages.
- **Loading Indicators**: `CircularProgress` is shown during status fetching and actions.

### Styling and Helper Functions

- **`getContainerStatusChipColor(status?: string)`**: Returns a MUI chip color (`success`, `error`, `warning`, `default`) based on the container status string.
- **`getServiceStatusChipColor(serviceStatus?: string | null)`**: Returns a MUI chip color based on the service health string.
- **`formatContainerName(name?: string)`**: Formats the raw container name (e.g., "movelook_elastic_search") into a more readable format (e.g., "Elastic Search").
- **`renderDetailRow(...)`**: Helper function to render rows within the status tables in each card, including an icon, label, and value.

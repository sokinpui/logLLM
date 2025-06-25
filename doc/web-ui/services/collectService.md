# Collect Service (`collectService.ts`)

## File: `frontend/src/services/collectService.ts`

### Overview

The `collectService.ts` module provides functions for interacting with the backend API endpoints related to log collection. This includes analyzing server directory structures and initiating/monitoring collection tasks. It utilizes the base `apiClient`.

### API Endpoint Prefix

- `const API_ENDPOINT = "/collect";`

### Interfaces

- **`ServerPathRequest`**:
  - `directory` (string): The absolute path on the server to be analyzed or from which to collect logs.

### Exported Functions

1.  **`analyzeServerPathStructure(params: ServerPathRequest): Promise<DirectoryAnalysisResponse>`**

    - **Purpose**: Requests the backend to analyze the structure of a given directory path on the server.
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/analyze-structure`
    - **Request Body**: `params` (of type `ServerPathRequest`)
    - **Response Type**: `DirectoryAnalysisResponse` (defined in `frontend/src/types/collect.ts`)
      - Includes `path_exists`, `root_files_present`, `identified_groups`, `error_message`, `scanned_path`.

2.  **`startCollectionFromServerPath(params: ServerPathRequest): Promise<MessageResponse & { task_id?: string }>`**

    - **Purpose**: Initiates a log collection task on the backend for the specified server directory.
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/from-server-path`
    - **Request Body**: `params` (of type `ServerPathRequest`)
    - **Response Type**: `MessageResponse` (from `frontend/src/types/api.ts`), potentially augmented with a `task_id` if the backend includes it directly in the response body (though the current implementation in `CollectPage.tsx` extracts it from the message string).

3.  **`getCollectionTaskStatus(taskId: string): Promise<TaskStatusResponse>`**
    - **Purpose**: Fetches the current status of an ongoing or completed collection task.
    - **Method**: `GET`
    - **Endpoint**: `${API_ENDPOINT}/task-status/${taskId}`
    - **Response Type**: `TaskStatusResponse` (defined in `frontend/src/types/collect.ts`)
      - Includes `task_id`, `status`, `progress_detail`, `completed`, `error`, `last_updated`, and potentially `collection_summary`.

### Usage Example (from `CollectPage.tsx`)

```typescript
// In CollectPage.tsx
import * as collectService from "../services/collectService";

// To analyze path
const analysisReqParams = { directory: serverDirectoryPath };
const analysisResp =
  await collectService.analyzeServerPathStructure(analysisReqParams);
setAnalysisResult(analysisResp);

// To start collection
const startReqParams = { directory: analysisResult.scanned_path };
const startResp =
  await collectService.startCollectionFromServerPath(startReqParams);
setSuccessMessage(startResp.message);
// ... extract task_id from startResp.message ...

// To get task status
const statusResp = await collectService.getCollectionTaskStatus(currentTaskId);
setCollectionStatus(statusResp);
```

This service encapsulates the API calls related to log collection, simplifying the logic in the `CollectPage` component.

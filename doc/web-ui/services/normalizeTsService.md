# Timestamp Normalizer Service (`normalizeTsService.ts`)

## File: `frontend/src/services/normalizeTsService.ts`

### Overview

The `normalizeTsService.ts` module provides functions to interact with the backend API endpoints for the timestamp normalization feature. This includes initiating tasks to normalize timestamps or remove timestamp fields from parsed logs, and fetching the status of these tasks.

### API Endpoint Prefix

- `const API_ENDPOINT = "/normalize-ts";`

### Exported Functions

1.  **`runNormalizeTsTask(params: NormalizeTsRunRequest): Promise<MessageResponse>`**

    - **Purpose**: Initiates a backend task to either normalize timestamps or remove the `@timestamp` field from documents in `parsed_log_<group_name>` indices.
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/run`
    - **Request Body**: `params` (of type `NormalizeTsRunRequest` from `frontend/src/types/normalizeTs.ts`). This object specifies the action (`normalize` or `remove_field`), target groups (single or all), optional limit per group, batch size, and confirmation for deletion.
    - **Response Type**: `MessageResponse` (from `frontend/src/types/api.ts`), typically containing a message about task initiation and the task ID.

2.  **`getNormalizeTsTaskStatus(taskId: string): Promise<NormalizeTsTaskStatusResponse>`**
    - **Purpose**: Fetches the current status and results of a previously initiated timestamp normalization or deletion task.
    - **Method**: `GET`
    - **Endpoint**: `${API_ENDPOINT}/task-status/${taskId}`
    - **Response Type**: `NormalizeTsTaskStatusResponse` (from `frontend/src/types/normalizeTs.ts`).
      - Includes `task_id`, `status`, `progress_detail`, `completed`, `error`, `last_updated`.
      - `result_summary`: A dictionary where keys are group names and values are `NormalizeTsTaskGroupResult` objects detailing the outcome for each processed group (docs scanned, updated, normalization errors).

### Usage Example (from `NormalizeTsPage.tsx`)

```typescript
// In NormalizeTsPage.tsx
import * as normalizeTsService from "../services/normalizeTsService";

// To run a normalization task
const runParams: NormalizeTsRunRequest = {
  action: "normalize",
  all_groups: true,
  group_name: null,
  limit_per_group: 100, // Optional
  batch_size: 5000,
};
const response = await normalizeTsService.runNormalizeTsTask(runParams);
// Extract task ID from response.message and store it...

// To get task status
const statusData =
  await normalizeTsService.getNormalizeTsTaskStatus(currentTaskId);
setTaskStatusObj(statusData);
```

This service allows the `NormalizeTsPage` to delegate API communication for managing timestamp processing tasks.

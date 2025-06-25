# Analyze Errors Service (`analyzeErrorsService.ts`)

## File: `frontend/src/services/analyzeErrorsService.ts`

### Overview

The `analyzeErrorsService.ts` module provides functions to interact with the backend API endpoints for the error log summarization pipeline. This includes initiating an analysis run, fetching the status of an ongoing task, and listing previously generated error summaries.

### API Endpoint Prefix

- `const API_ENDPOINT = "/analyze-errors";`

### Exported Functions

1.  **`runErrorSummaryAnalysis(params: AnalyzeErrorsRunParams): Promise<TaskInitiationResponse>`**

    - **Purpose**: Initiates a backend task to perform error log summarization for a given group and time window, with various configurable parameters.
    - **Method**: `POST`
    - **Endpoint**: `${API_ENDPOINT}/run-summary`
    - **Request Body**: `params` (of type `AnalyzeErrorsRunParams` from `frontend/src/types/analyzeErrors.ts`). This object includes `group_name`, time window, error levels, model names, clustering parameters, sampling parameters, and target index.
    - **Response Type**: `TaskInitiationResponse` (from `frontend/src/types/analyzeErrors.ts`), containing `task_id` and an initiation message.

2.  **`getErrorAnalysisTaskStatus(taskId: string): Promise<AnalyzeErrorsTaskStatusResponse>`**

    - **Purpose**: Fetches the current status and results of a previously initiated error analysis task.
    - **Method**: `GET`
    - **Endpoint**: `${API_ENDPOINT}/task-status/${taskId}`
    - **Response Type**: `AnalyzeErrorsTaskStatusResponse` (from `frontend/src/types/analyzeErrors.ts`).
      - Includes `task_id`, `status`, `progress_detail`, `completed`, `error`, `last_updated`.
      - `result_summary`: An `AnalysisResultSummary` object containing the agent's final status, details of processed clusters (with their LLM summaries), counts of summaries stored, and any errors encountered during the run.

3.  **`listGeneratedErrorSummaries(params?: object): Promise<ListErrorSummariesResponse>`**
    - **Purpose**: Retrieves a list of previously generated error summaries from the storage index (default: `log_error_summaries`).
    - **Method**: `GET`
    - **Endpoint**: `${API_ENDPOINT}/list-summaries`
    - **Query Parameters (optional, passed in `params` object)**:
      - `group_name` (string)
      - `start_time` (string, ISO format)
      - `end_time` (string, ISO format)
      - `limit` (number)
      - `offset` (number)
      - `sort_by` (string, e.g., "generation_timestamp")
      - `sort_order` ("asc" | "desc")
    - **Response Type**: `ListErrorSummariesResponse` (from `frontend/src/types/analyzeErrors.ts`).
      - Contains an array of `ErrorSummaryListItem` objects, `total` count, `offset`, and `limit`.

### Usage Example (from `AnalyzeErrorsPage.tsx`)

```typescript
// In AnalyzeErrorsPage.tsx
import * as analyzeErrorsService from "../services/analyzeErrorsService";

// To run an analysis
const runParams: AnalyzeErrorsRunParams = {
  /* ... populated from form ... */
};
const initResponse =
  await analyzeErrorsService.runErrorSummaryAnalysis(runParams);
setTaskId(initResponse.task_id);

// To get task status
const statusData =
  await analyzeErrorsService.getErrorAnalysisTaskStatus(currentTaskId);
setTaskStatusObj(statusData);

// To list summaries
const listParams = { group_name: "apache", limit: 10, offset: 0 };
const summariesResponse =
  await analyzeErrorsService.listGeneratedErrorSummaries(listParams);
setListedSummaries(summariesResponse.summaries);
setListTotalRows(summariesResponse.total);
```

This service enables the `AnalyzeErrorsPage` to manage the complex error summarization workflow through clear API calls.

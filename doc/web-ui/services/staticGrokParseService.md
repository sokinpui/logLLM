# Static Grok Parser Service (`staticGrokParseService.ts`)

## File: `frontend/src/services/staticGrokParseService.ts`

### Overview

The `staticGrokParseService.ts` module handles API interactions for the static Grok parsing feature. This includes initiating parsing runs, fetching task statuses, listing historical parsing statuses for files/groups, and deleting previously parsed data.

### API Endpoint Prefix

- `const API_PREFIX = "/static-grok-parser";`

### Interfaces (Type Definitions)

- **`StaticGrokRunRequest`**:
  - `group_name?: string | null`
  - `all_groups?: boolean`
  - `clear_previous_results?: boolean`
  - `grok_patterns_file_path_on_server: string` (Path to the YAML file on the server)
- **`StaticGrokTaskInfo`**:
  - `task_id: string`
  - `message: string`
- **`StaticGrokTaskStatus`**:
  - `task_id: string`
  - `status: string`
  - `progress_detail?: string | null`
  - `completed: boolean`
  - `error?: string | null`
  - `last_updated?: string | null`
  - `result_summary?: Record<string, any> | null` (Contains orchestrator status and per-group summaries)
- **`StaticGrokParseStatusItem`**:
  - `log_file_id: string`
  - `group_name?: string | null`
  - `log_file_relative_path?: string | null`
  - `last_line_number_parsed_by_grok: number`
  - `last_total_lines_by_collector: number`
  - `last_parse_timestamp?: string | null`
  - `last_parse_status?: string | null`
- **`StaticGrokStatusListResponse`**:
  - `statuses: StaticGrokParseStatusItem[]`
  - `total: number`
- **`StaticGrokDeleteRequest`**:
  - `group_name?: string | null`
  - `all_groups?: boolean`

### Exported Functions

1.  **`runStaticGrokParser(params: StaticGrokRunRequest): Promise<StaticGrokTaskInfo>`**

    - **Purpose**: Initiates a static Grok parsing run on the backend.
    - **Method**: `POST`
    - **Endpoint**: `${API_PREFIX}/run`
    - **Request Body**: `params` (of type `StaticGrokRunRequest`)
    - **Response Type**: `StaticGrokTaskInfo`

2.  **`getStaticGrokTaskStatus(taskId: string): Promise<StaticGrokTaskStatus>`**

    - **Purpose**: Fetches the status of a specific static Grok parsing task.
    - **Method**: `GET`
    - **Endpoint**: `${API_PREFIX}/task-status/${taskId}`
    - **Response Type**: `StaticGrokTaskStatus`

3.  **`listStaticGrokStatuses(groupName?: string): Promise<StaticGrokStatusListResponse>`**

    - **Purpose**: Retrieves a list of parsing statuses for log files, optionally filtered by group name.
    - **Method**: `GET`
    - **Endpoint**: `${API_PREFIX}/list-status` (appends `?group_name=<groupName>` if provided)
    - **Response Type**: `StaticGrokStatusListResponse`

4.  **`deleteStaticGrokParsedData(params: StaticGrokDeleteRequest): Promise<MessageResponse>`**
    - **Purpose**: Deletes previously parsed data (from `parsed_log_*`, `unparsed_log_*` indices) and status entries (from `static_grok_parse_status`) for specified groups.
    - **Method**: `POST`
    - **Endpoint**: `${API_PREFIX}/delete-parsed-data`
    - **Request Body**: `params` (of type `StaticGrokDeleteRequest`)
    - **Response Type**: `MessageResponse` (from `frontend/src/types/api.ts`)

### Deprecated/Removed Functions

The service previously included `getGrokPatternsFile` and `updateGrokPatternsFile` for directly managing the Grok patterns YAML file via the API. These are no longer used by the primary UI flow for running the parser, which now relies on a server-side file path for patterns. If these backend endpoints are removed, these service functions should also be removed from the frontend code.

```typescript
// Potentially deprecated if backend endpoints are removed:
// export const getGrokPatternsFile = async (): Promise<GrokPatternsFileResponse> => { ... };
// export const updateGrokPatternsFile = async (file: File): Promise<MessageResponse> => { ... };
```

This service provides the necessary functions for the `StaticGrokParserPage` to manage and monitor parsing tasks.

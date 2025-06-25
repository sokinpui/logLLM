# Timestamp Normalizer Page (`NormalizeTsPage.tsx`)

## File: `frontend/src/pages/NormalizeTsPage.tsx`

### Overview

The `NormalizeTsPage` component provides a user interface for interacting with the `TimestampNormalizerAgent` in the backend. It allows users to either:

1.  **Normalize Timestamps**: Process parsed logs (`parsed_log_<group_name>`) to find, parse, and standardize various timestamp formats into a UTC ISO 8601 string, storing it in the `@timestamp` field of the documents (in-place update).
2.  **Delete @timestamp Field**: Remove the `@timestamp` field from documents in `parsed_log_<group_name>` indices.

The page manages the configuration for these actions, initiates backend tasks, and displays their progress and results.

### Key Features

- **Action Selection**: Dropdown to choose between "Normalize Timestamps" and "Delete @timestamp Field".
- **Group Targeting**:
  - Switch to process "All Groups".
  - If not all groups, a dropdown allows selection of a specific group.
- **Normalization Options (for "normalize" action)**:
  - Optional `TextField` to limit the number of documents processed per group (for testing).
- **Batch Size Configuration**: `TextField` to set the batch size for Elasticsearch operations.
- **Deletion Confirmation (for "remove_field" action)**:
  - A `Switch` to "Confirm Deletion".
  - A `window.confirm` dialog is also shown if the switch isn't pre-checked, as a safety measure.
- **Task Initiation**: "Run Normalization" / "Run Deletion" button to start the backend task.
- **Task Progress Display**:
  - Shows Task ID.
  - `LinearProgress` bar for visual feedback.
  - Displays current status, details, and any errors.
  - Upon successful completion, shows a summary of results per group (documents scanned, updated, normalization errors).
- **State Persistence**: Form inputs and task details are saved to local storage.

### State Management

- **Action Configuration**:
  - `action` ('normalize' | 'remove_field'): The selected operation.
  - `groupName` (string): Target group for single-group operation.
  - `allGroups` (boolean): Flag to process all groups.
  - `limitPerGroup` (string): Max documents per group for normalization (input as string, parsed to int).
  - `batchSize` (number): Batch size for ES operations.
  - `confirmDelete` (boolean): Flag for confirming deletion action.
- **Task State**:
  - `taskId` (string | null): ID of the active or last run task.
  - `taskStatusObj` (NormalizeTsTaskStatusResponse | null): Detailed status and results of the task.
- **UI & General State**:
  - `allDbGroups` (Array<GroupInfoDetail>): List of groups for the dropdown.
  - `loadingRun` (boolean): Loading state for task initiation.
  - `pageError`, `pageSuccess` (string | null): For user messages.

### Core Logic and Event Handlers

- **Local Storage Effects**: `useEffect` hooks persist form inputs and task state.
- **`fetchGroupsForDropdown()`**: Fetches all group names via `groupService` for selection.
- **`handleRunTask()`**:
  - Validates inputs (e.g., group selection if not `allGroups`).
  - Handles confirmation for "remove_field" action.
  - Constructs `NormalizeTsRunRequest` parameters.
  - Calls `normalizeTsService.runNormalizeTsTask()` to start the backend task.
  - Updates `taskId` and initializes `taskStatusObj`.
- **`fetchCurrentTaskStatus()`**: Polls `normalizeTsService.getNormalizeTsTaskStatus()` for updates on an active task.
- **Polling Logic (in `useEffect`)**: Manages interval polling for `fetchCurrentTaskStatus` if a task is running.
- **`renderGroupResult(groupName, result)`**: A helper function to display the processing summary for a single group from `taskStatusObj.result_summary`.

### UI Elements

- **Main Paper Container**: Wraps page content.
- **Configuration Section**:
  - `Select` for "Action" (Normalize/Delete).
  - `Switch` for "Process All Groups".
  - `TextField` (select) for specific group selection.
  - `TextField` for "Limit per Group" (visible for "normalize" action).
  - `TextField` for "Batch Size".
  - `Switch` for "Confirm Deletion" (visible for "remove_field" action), styled with error color when active.
  - "Run" `Button` with dynamic text and loading state.
- **Task Progress Section**:
  - Displays Task ID.
  - `LinearProgress` bar.
  - Status chip, progress details, and error alert.
  - **Results Accordion**: Upon successful completion, shows an accordion with `renderGroupResult` output for each processed group, detailing scanned/updated counts and normalization errors.

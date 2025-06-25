# Analyze Errors Page (`AnalyzeErrorsPage.tsx`)

## File: `frontend/src/pages/AnalyzeErrorsPage.tsx`

### Overview

The `AnalyzeErrorsPage` component provides a user interface for the error log summarization pipeline. Users can configure parameters for fetching, clustering, and summarizing error logs from a specific group within a defined time window. The page allows users to initiate the analysis, monitor its progress, view the results (including generated summaries per cluster), and list previously generated summaries.

### Key Features

- **Run Configuration**:
  - Selection of a target log group.
  - Date/Time pickers for setting the analysis time window (start and end times, UTC).
  - Input for error log levels (comma-separated string).
  - **Advanced Options (collapsible section)**:
    - Max logs to process.
    - Embedding model name (local or API).
    - LLM model for summaries.
    - Target Elasticsearch index for storing summaries.
    - DBSCAN clustering parameters (`eps`, `min_samples`).
    - Sampling parameters (`max_samples_per_cluster`, `max_samples_unclustered`).
- **Analysis Initiation**: "Run Error Analysis" button to start the backend task.
- **Task Progress Display**:
  - Shows Task ID.
  - `LinearProgress` bar indicating approximate progress through stages (Fetching, Embedding, Clustering, Summarizing).
  - Displays current status, details, and any errors from the backend task.
  - **Results Accordion**: Upon successful completion, displays a detailed summary:
    - Agent's final status, raw logs fetched count, total summaries stored count.
    - Any errors encountered by the agent during the run.
    - An accordion for each processed cluster/group, showing:
      - Cluster label and total logs.
      - Time range of logs in the cluster.
      - LLM-generated summary (text, potential cause, keywords, representative log).
      - Elasticsearch ID of the stored summary document.
      - A sample of log messages used as input for the LLM.
- **List Previously Generated Summaries**:
  - An accordion section to display summaries already stored in Elasticsearch.
  - Filtering by group name.
  - Pagination for browsing through summaries.
  - Refresh button to update the list.
  - Table displays key fields: Group, Cluster, Summary Text, Keywords, Generated At, Samples/Total logs in cluster.
- **State Persistence**: Most form inputs, task details, and list filters are persisted in local storage.

### State Management

- **Run Parameters**: States for `groupName`, `startTime`, `endTime`, `errorLevels`, and all advanced options (e.g., `maxLogsToProcess`, `embeddingModelName`, etc.).
- **Task State**:
  - `taskId` (string | null): ID of the active or last analysis task.
  - `taskStatusObj` (AnalyzeErrorsTaskStatusResponse | null): Detailed status and results of the task.
- **UI State**:
  - `allDbGroups` (Array<GroupInfoDetail>): For group selection dropdown.
  - `loadingRun` (boolean): Loading state for initiating analysis.
  - `pageError`, `pageSuccess` (string | null): For user messages.
  - `showAdvanced` (boolean): Toggles visibility of advanced options.
- **Listed Summaries State**:
  - `listedSummaries` (Array<ErrorSummaryListItem>): Summaries fetched from ES.
  - `loadingListedSummaries` (boolean): Loading state for the list.
  - `listError` (string | null): Error message for the list fetching.
  - `listPage`, `listRowsPerPage`, `listTotalRows` (number): For pagination.
  - `listFilterGroup` (string): Group name filter for the list.

### Core Logic and Event Handlers

- **Local Storage Effects**: Numerous `useEffect` hooks persist form states, task details, and list configurations.
- **`fetchGroupsForDropdown()`**: Fetches all group names via `groupService` for the selection dropdown.
- **`handleRunAnalysis()`**:
  - Validates inputs (group selected, start time < end time).
  - Constructs `AnalyzeErrorsRunParams` from the current state.
  - Calls `analyzeErrorsService.runErrorSummaryAnalysis()` to start the backend task.
  - Updates `taskId` and initializes `taskStatusObj`.
- **`fetchCurrentTaskStatus()`**: Polls `analyzeErrorsService.getErrorAnalysisTaskStatus()` for updates on an active task. If the task completes successfully, it also calls `fetchListedSummaries()` to refresh the list of summaries.
- **Polling Logic (in `useEffect`)**: Manages interval polling for `fetchCurrentTaskStatus` if a task is running.
- **`renderClusterDetail(cluster, index)`**: Helper function to render the accordion details for a single processed cluster from `taskStatusObj.result_summary.processed_cluster_details`.
- **`fetchListedSummaries(showLoadingSpinner)`**: Fetches previously generated summaries from `analyzeErrorsService.listGeneratedErrorSummaries()` based on current filters and pagination state.
- **Pagination Handlers**: `handleChangeListPage`, `handleChangeListRowsPerPage` for the summaries table.

### UI Elements

- **Main Container**: `LocalizationProvider` for date/time pickers.
- **Configuration Paper**:
  - `TextField` (select) for "Target Group".
  - `TextField` for "Error Levels".
  - `DateTimePicker` for "Start Time" and "End Time".
  - `Switch` to toggle "Show Advanced Options".
  - **Advanced Options `Collapse`**: Contains `TextField` inputs for all advanced parameters.
  - "Run Error Analysis" `Button` with loading/disabled states.
- **Task Status Paper**:
  - Displays Task ID, `LinearProgress` bar, status chip, details, and error alert.
  - **Results Accordion**: Shows overall agent status, counts, and then nested accordions for each `ProcessedClusterDetail`.
- **Previously Generated Summaries Paper**:
  - Title and Refresh button.
  - `TextField` to filter summaries by group name.
  - `TableContainer` with a `Table` to display `ErrorSummaryListItem` data.
  - `TablePagination` component.

# Collect Logs Page (`CollectPage.tsx`)

## File: `frontend/src/pages/CollectPage.tsx`

### Overview

The `CollectPage` component provides the UI for users to initiate the log collection process from a specified directory path on the server. It involves two main steps:

1.  **Analyzing Path Structure**: The user inputs a server directory path, and the system analyzes it to identify potential log groups (subdirectories containing log files).
2.  **Starting Collection**: If the path analysis is successful and the structure is valid (no logs in the root, at least one group found), the user can start the collection process.

The page also handles displaying the progress and status of an ongoing or completed collection task.

### Key Features

- **Path Input**: A `TextField` for users to enter the absolute server directory path.
- **Path Analysis**:
  - A button ("Analyze Path") triggers an API call (`collectService.analyzeServerPathStructure`) to the backend.
  - Displays the analysis results, including whether the path exists, if root files are present (which blocks collection), and a list of identified log groups with file counts.
- **Collection Initiation**:
  - A button ("Start Collection") becomes active if path analysis is successful and the structure is valid.
  - Triggers an API call (`collectService.startCollectionFromServerPath`) to the backend to start the asynchronous collection task.
- **Task Progress Display**:
  - Once collection is initiated, a task ID is received.
  - The component polls the backend (`collectService.getCollectionTaskStatus`) at regular intervals to update and display the task's status, progress details, and any errors.
  - Uses a `LinearProgress` bar to visualize progress.
- **User Feedback**: `Alert` components are used for error and success messages.
- **State Persistence**: The server directory path, last analysis result, collection task ID, and collection status are persisted in local storage to maintain state across sessions or page reloads.

### State Management

- `serverDirectoryPath` (string): The path entered by the user.
- `analysisResult` (DirectoryAnalysisResponse | null): Stores the response from the path analysis API.
- `isAnalyzingPath` (boolean): Loading state for path analysis.
- `collectionTaskId` (string | null): The ID of the currently active or last run collection task.
- `collectionStatus` (TaskStatusResponse | null): Stores the detailed status of the collection task.
- `isStartingCollection` (boolean): Loading state when initiating collection.
- `isPollingStatus` (boolean): Indicates if the frontend is actively polling for task status.
- `error` (string | null): For displaying error messages.
- `successMessage` (string | null): For displaying success messages.

### Core Logic and Event Handlers

- **Local Storage Effects**: `useEffect` hooks manage saving and retrieving state variables (path, analysis result, task ID, task status) from local storage.
- **`extractTaskIdFromMessage(message: string)`**: A helper to parse the task ID from the API's success message if it's embedded there.
- **`handleAnalyzePath()`**:
  - Validates that `serverDirectoryPath` is not empty.
  - Resets relevant states (analysisResult, taskId, status, error, success).
  - Calls `collectService.analyzeServerPathStructure`.
  - Updates `analysisResult` and `error` based on the API response.
- **`handleStartCollection()`**:
  - Validates `analysisResult` (path exists, no root files, at least one group).
  - Resets task-related states.
  - Calls `collectService.startCollectionFromServerPath`.
  - Sets `successMessage` and extracts/sets `collectionTaskId` from the response.
- **Polling Logic (in `useEffect`)**:
  - Triggers if `collectionTaskId` exists and the task is not marked as completed.
  - Sets `isPollingStatus` to `true`.
  - Defines an async `poll` function that calls `collectService.getCollectionTaskStatus(collectionTaskId)`.
  - Updates `collectionStatus`. If the task is completed or errors out, it clears the polling interval and updates `successMessage` or `error`.
  - The `poll` function is called immediately and then at 3-second intervals.
  - The interval is cleared when the component unmounts or if the task completes.

### UI Elements

- **Path Input Section**: `TextField` for path and "Analyze Path" `Button`.
- **Analysis Result Card**: Displays the `analysisResult` if available.
  - Shows the scanned path.
  - Alerts for path non-existence or analysis errors.
  - Warning if root files are present.
  - Lists identified groups (`FolderZipIcon` and group name/file count).
  - Success alert if structure is valid for collection.
- **Start Collection Button**: Enabled based on `analysisResult` validity. Shows loading state.
- **Task Progress Section**: Displayed if `collectionTaskId` is set.
  - Shows Task ID.
  - `LinearProgress` bar.
  - Textual status and details.
  - Alerts for task errors or success upon completion.
- **Instructions**: A simple ordered list guiding the user through the collection process.

# Static Grok Parser Page (`StaticGrokParserPage.tsx`)

## File: `frontend/src/pages/StaticGrokParserPage.tsx`

### Overview

The `StaticGrokParserPage` provides a user interface for managing and running the static Grok parsing process on logs stored in Elasticsearch. This involves specifying a Grok patterns file on the server, selecting target log groups, and initiating parsing runs. It also allows users to view the parsing status of individual log files and delete previously parsed data.

### Key Features

- **Grok Patterns File Configuration**:
  - Input field for specifying the **absolute path** to a Grok patterns YAML file on the server.
  - A "Confirm Path" button to validate the path format (absolute and ends with `.yaml`/`.yml`) and lock it in for the run. This path is crucial as the backend agent will use it.
- **Run Parser Section**:
  - Option to parse a single selected group or all groups.
  - Dropdown (Select) to choose a specific group if not parsing all.
  - Switch to "Clear previous parsed data & status" before a run.
  - Button to "Start Parsing Run", which initiates a backend task.
- **Task Progress Display**:
  - Shows the status and progress details of an ongoing or completed parsing task.
  - Includes Task ID and a summary of orchestrator and group-level results upon completion.
- **View Parsing Statuses Section**:
  - Accordion to show/hide this section.
  - Dropdown to filter status entries by group.
  - Button to "List Statuses" which fetches and displays a table of `StaticGrokParseStatusItem`.
  - Table shows Group, File Path, Grok Line, Collector Line, Last Status, and Last Parsed Timestamp.
- **Danger Zone - Delete Parsed Data Section**:
  - Accordion to show/hide this critical section.
  - Option to delete data for a single selected group or all groups.
  - Button to "Delete Parsed Data & Status", which requires confirmation.
- **State Persistence**: Many form inputs and task details are persisted in local storage.

### State Management

- **Run Configuration**:
  - `runGroupName` (string): Selected group for a single-group run.
  - `runAllGroups` (boolean): Flag to run for all groups.
  - `clearPrevious` (boolean): Flag to clear data before running.
  - `grokPatternsFilePathOnServer` (string): Path to the Grok patterns YAML on the server.
  - `serverPathConfirmed` (boolean): True if the server path has been confirmed by the user.
- **Task State**:
  - `taskId` (string | null): ID of the active or last parsing task.
  - `taskStatusObj` (StaticGrokTaskStatus | null): Detailed status of the task.
- **Status Listing**:
  - `statusList` (Array<StaticGrokParseStatusItem>): List of fetched parsing statuses.
  - `filterStatusGroup` (string): Group name to filter the status list.
- **Deletion Configuration**:
  - `deleteGroupName` (string): Selected group for deletion.
  - `deleteAllGroupsData` (boolean): Flag to delete data for all groups.
- **UI & General State**:
  - `allDbGroups` (Array<GroupInfoDetail>): List of all available groups for dropdowns.
  - `loadingRun`, `loadingStatusList`, `loadingDelete` (booleans): Loading indicators for actions.
  - `pageError`, `pageSuccess` (string | null): For displaying messages.

### Core Logic and Event Handlers

- **Local Storage Effects**: Numerous `useEffect` hooks manage persistence of form states and task details.
- **`fetchGroupsForDropdown()`**: Fetches all group names from `groupService` for populating select dropdowns.
- **`handleConfirmServerPath()`**: Validates the `grokPatternsFilePathOnServer` (must be absolute, YAML/YML extension) and sets `serverPathConfirmed`.
- **`handleRunParser()`**:
  - Validates that `grokPatternsFilePathOnServer` is provided and confirmed.
  - Constructs `StaticGrokRunRequest` parameters.
  - Calls `staticGrokService.runStaticGrokParser()` to start the backend task.
  - Updates `taskId` and initializes `taskStatusObj`.
- **`fetchCurrentTaskStatus()`**: Polls `staticGrokService.getStaticGrokTaskStatus()` to update `taskStatusObj`. Stops polling if task is completed or errors.
- **`handleListStatuses()`**: Calls `staticGrokService.listStaticGrokStatuses()` to fetch and display parsing statuses.
- **`handleDeleteData()`**:
  - Confirms deletion with the user (if not auto-confirmed).
  - Constructs `StaticGrokDeleteRequest`.
  - Calls `staticGrokService.deleteStaticGrokParsedData()`.
  - Refreshes the status list upon success.

### UI Elements

- The page is structured with Accordions for "Grok Patterns Source", "View Parsing Statuses", and "Danger Zone".
- **Grok Patterns Source**:
  - `TextField` for server path input.
  - "Confirm Path" `Button`.
- **Run Parser Paper**:
  - `Switch` for "Parse All Groups".
  - `TextField` (select) for single group selection (if not all groups).
  - `Switch` for "Clear previous".
  - "Start Parsing Run" `Button` with loading indicator.
- **Task Progress Paper**: Displays `taskId`, status chip, progress detail, error alert, and a summary of results upon completion.
- **View Parsing Statuses Accordion**:
  - `TextField` (select) to filter by group.
  - "List Statuses" `Button`.
  - `TableContainer` to display status items (`group_name`, `log_file_relative_path`, `last_line_number_parsed_by_grok`, etc.).
- **Danger Zone Paper**:
  - Styled with error theme colors.
  - `Switch` for "Delete for ALL Groups".
  - `TextField` (select) for single group deletion.
  - "Delete Parsed Data & Status" `Button` (error color).
  - Warning text about irreversibility.

### Important Notes

- The "Grok Patterns File Path on Server" is critical. The backend agent reads this file from the server's filesystem. The UI does not upload the file content itself for the `run` operation.
- The "Confirm Path" step is a UI validation to ensure the user provides a path in the correct format before attempting to run the parser.

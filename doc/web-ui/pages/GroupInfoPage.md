# Group Information Page (`GroupInfoPage.tsx`)

## File: `frontend/src/pages/GroupInfoPage.tsx`

### Overview

The `GroupInfoPage` component is responsible for displaying information about the log groups that have been identified and processed by the `logLLM` system's collector. This typically includes the group name and the number of log files associated with it.

### Key Features

- **Data Fetching**: Retrieves group information from the backend API endpoint that lists all collected groups (usually from the `group_infos` Elasticsearch index).
- **Tabular Display**: Presents the group information in a clear, tabular format using Material UI's `Table` components.
- **Loading State**: Shows a `CircularProgress` indicator while data is being fetched.
- **Error Handling**: Displays an `Alert` message if fetching group information fails.
- **Empty State**: Shows an informational message if no groups are found.
- **Refresh**: Includes a refresh button to re-fetch the group list.

### State Management

- `groups` (Array<GroupInfoDetail>): Stores the list of group information objects fetched from the API.
- `loading` (boolean): Indicates whether the data fetching process is currently active.
- `error` (string | null): Stores any error message encountered during data fetching.

### Core Logic and Event Handlers

- **`fetchGroupInfo(showLoadingSpinner: boolean)`**:
  - An asynchronous function, wrapped in `useCallback` for memoization.
  - Sets `loading` to `true` if `showLoadingSpinner` is true.
  - Clears any previous `error`.
  - Calls the `groupService.listAllGroupsInfo()` function to fetch data from the backend.
  - Updates the `groups` state with the fetched data.
  - Handles potential errors by setting the `error` state and clearing the `groups` state.
  - Sets `loading` to `false` in the `finally` block.
- **`useEffect` Hook**:
  - Calls `fetchGroupInfo()` when the component mounts to initially load the group data. The dependency array `[fetchGroupInfo]` ensures it re-runs if `fetchGroupInfo` itself changes (which it won't in this typical setup, but is good practice).

### UI Elements

- **Main Paper Container**: Wraps the entire page content.
- **Title**: "Collected Group Information".
- **Refresh Button**: An `IconButton` with a `<RefreshIcon />` to trigger `fetchGroupInfo(true)`.
- **Description**: A brief text explaining the purpose of the page.
- **Error Alert**: Displays the `error` message if not null.
- **Loading Indicator**: A `CircularProgress` displayed centrally when `loading` is true.
- **Empty State Alert**: An `Alert` with severity "info" displayed if `groups` is empty and there's no error.
- **Table**:
  - `TableContainer` wrapping a MUI `Table`.
  - `TableHead`: Contains a header row with "Group Name" and "File Count" cells, styled with icons.
  - `TableBody`:
    - Maps over the `groups` array.
    - For each `group` object, renders a `TableRow`.
    - `TableCell` for Group Name: Displays the `group.group_name` typically styled with a `Chip`.
    - `TableCell` for File Count: Displays `group.file_count`, aligned to the right.

### Styling

- Uses Material UI components for layout and styling (e.g., `Paper`, `Table`, `Chip`).
- Icons (`FolderIcon`, `DescriptionIcon`) are used in table headers for visual cues.
- Table rows have a hover effect.

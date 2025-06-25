# Group Service (`groupService.ts`)

## File: `frontend/src/services/groupService.ts`

### Overview

The `groupService.ts` module is responsible for fetching information about log groups that have been identified and stored by the `logLLM` system (typically in the `group_infos` Elasticsearch index via the Collector).

### API Endpoint Prefix

- `const API_ENDPOINT = "/groups";`

### Exported Functions

1.  **`listAllGroupsInfo(): Promise<GroupInfoListResponse>`**
    - **Purpose**: Retrieves a list of all known log groups and basic information about them (like file count).
    - **Method**: `GET`
    - **Endpoint**: `${API_ENDPOINT}/`
    - **Response Type**: `GroupInfoListResponse` (defined in `frontend/src/types/group.ts`)
      - Contains an array of `GroupInfoDetail` objects. Each `GroupInfoDetail` includes `group_name` and `file_count`.

### Usage Example (from `GroupInfoPage.tsx` or other pages needing group lists)

```typescript
// In GroupInfoPage.tsx
import * as groupService from "../services/groupService";

// To fetch all group information
const response = await groupService.listAllGroupsInfo();
setGroups(response.groups); // Assuming 'groups' is a state variable
```

This service provides a simple way for frontend components to get a list of available log groups, often used for populating dropdown menus or displaying overview information.

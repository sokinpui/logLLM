# Base API Client (`apiClient`)

## File: `frontend/src/services/api.ts`

### Overview

The `api.ts` file defines a generic `apiClient` function that serves as the foundation for all HTTP requests made from the frontend to the `logLLM` backend API. It standardizes request construction, error handling, and JSON parsing.

### `API_BASE_URL`

- **Type**: `string`
- **Source**:
  - Primarily read from the Vite environment variable `import.meta.env.VITE_API_BASE_URL`.
  - Falls back to `"http://localhost:8000/api"` if the environment variable is not set. This allows for easy configuration of the backend API URL depending on the deployment environment (development, staging, production).
- **Purpose**: Defines the base URL for all API requests.

### `apiClient<T>(endpoint: string, options?: RequestInit): Promise<T>`

- **Purpose**: An asynchronous generic function to make HTTP requests.
- **Type Parameter `<T>`**: Represents the expected type of the successful JSON response.
- **Parameters**:
  - `endpoint` (string): The API endpoint path (e.g., `/container/status`, `/collect/analyze-structure`). This is appended to `API_BASE_URL`.
  - `options` (RequestInit, optional): Standard `fetch` API options (e.g., `method`, `body`, custom `headers`).
- **Logic**:
  1.  Constructs the full URL by combining `API_BASE_URL` and the provided `endpoint`.
  2.  Merges default headers (`"Content-Type": "application/json"`) with any custom headers provided in `options`.
  3.  Makes the HTTP request using the `fetch` API.
  4.  **Error Handling**:
      - Checks if `response.ok` (status code in the 200-299 range).
      - If not `ok`, it attempts to parse the response body as JSON to extract an error message (often from a `detail` field in FastAPI error responses).
      - If JSON parsing fails, it uses a generic "Request failed" message.
      - Throws an `Error` with the extracted or generic error message.
  5.  **Success Handling**:
      - If `response.ok` is true, it parses the response body as JSON using `response.json()`.
      - Returns the parsed JSON data, typed as `T`.

### Usage Example (within other service files)

```typescript
// In services/containerService.ts
import apiClient from "./api";
import type { ContainerStatusResponse } from "../types/api";

const API_ENDPOINT = "/container";

export const getContainerStatus =
  async (): Promise<ContainerStatusResponse> => {
    return apiClient<ContainerStatusResponse>(`${API_ENDPOINT}/status`); // GET request by default
  };

export const startContainers = async (): Promise<MessageResponse> => {
  return apiClient<MessageResponse>(`${API_ENDPOINT}/start`, {
    method: "POST", // Specifying method for POST
  });
};
```

This centralized client ensures consistency in how API calls are made and how responses/errors are initially processed.

# Frontend API Services

This section documents the service modules used by the `logLLM` frontend to communicate with the backend API. Each service typically groups API calls related to a specific feature or resource.

Services are located in the `frontend/src/services/` directory.

## Base API Client

- **[`apiClient`](./api.md)** (`api.ts`): Describes the base `apiClient` function used by all other services to make HTTP requests to the backend.

## Specific Services

- **[`Container Service`](./containerService.md)** (`containerService.ts`): Handles API calls related to managing Docker containers for backend services (Elasticsearch, Kibana).
- **[`Collect Service`](./collectService.md)** (`collectService.ts`): Manages API interactions for log collection tasks, including path analysis and task status polling.
- **[`Group Service`](./groupService.md)** (`groupService.ts`): Fetches information about collected log groups.
- **[`Static Grok Parser Service`](./staticGrokParseService.md)** (`staticGrokParseService.ts`): Interacts with APIs for static Grok parsing, including running parsers, listing statuses, and deleting data.
- **[`Timestamp Normalizer Service`](./normalizeTsService.md)** (`normalizeTsService.ts`): Handles API calls for timestamp normalization and field removal tasks.
- **[`Analyze Errors Service`](./analyzeErrorsService.md)** (`analyzeErrorsService.ts`): Manages API interactions for the error log summarization pipeline, including running analyses and listing summaries.

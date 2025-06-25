# Page Components

This section provides documentation for the individual page components that make up the views of the `logLLM` frontend application. Each page is typically responsible for a specific feature or set of related functionalities.

Pages are located in the `frontend/src/pages/` directory.

## Available Pages

- **[Dashboard Page](./DashboardPage.md)** (`DashboardPage.tsx`): The main landing page, intended to display key metrics and summaries.
- **[Container Management Page](./ContainerPage.md)** (`ContainerPage.tsx`): Allows users to manage backend service containers (Elasticsearch, Kibana).
- **[Collect Logs Page](./CollectPage.md)** (`CollectPage.tsx`): Interface for collecting logs from server paths or via upload.
- **[Group Information Page](./GroupInfoPage.md)** (`GroupInfoPage.tsx`): Displays information about collected log groups.
- **[Static Grok Parser Page](./StaticGrokParserPage.md)** (`StaticGrokParserPage.tsx`): Interface for parsing logs in Elasticsearch using static Grok patterns.
- **[Timestamp Normalizer Page](./NormalizeTsPage.md)** (`NormalizeTsPage.tsx`): Tools for normalizing timestamps in parsed logs.
- **[Analyze Errors Page](./AnalyzeErrorsPage.md)** (`AnalyzeErrorsPage.tsx`): Interface for running the error log summarization pipeline.
- **[Not Found Page](./NotFoundPage.md)** (`NotFoundPage.tsx`): A fallback page displayed for invalid URLs.

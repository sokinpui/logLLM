# LogLLM: Comprehensive Development Guideline

## 1. Introduction

### 1.1 Project Purpose and Goals

`logLLM` is a system designed for advanced log management and analysis. Its primary goals are:

- To efficiently collect and store large volumes of log data.
- To parse and structure raw logs into a queryable format.
- To leverage Large Language Models (LLMs) for intelligent tasks such_as:
  - Assisting in Grok pattern generation (though current emphasis is on static patterns).
  - Summarizing complex error patterns.
  - Facilitating natural language queries over log data (future).
- To provide both a powerful Command Line Interface (CLI) for power users and automation, and a user-friendly Web UI for broader accessibility.

### 1.2 Target Audience for this Document

This guide is intended for anyone who will be contributing to the development, maintenance, or extension of the `logLLM` system.

## 2. Architecture Overview

`logLLM` consists of several key components that work together:

### 2.1 Backend (Python)

- **CLI (`src/logllm/cli/`)**:
  - The main entry point for users to interact with `logLLM` from the command line.
  - Built using `argparse`.
  - Orchestrates calls to various agents and utilities.
  - The main script is `src/logllm/cli/__main__.py`.
- **Agents (`src/logllm/agents/`)**:
  - Encapsulate complex processing logic.
  - Many agents (e.g., `StaticGrokParserAgent`, `ErrorSummarizerAgent`, `TimestampNormalizerAgent`) are implemented using **LangGraph**, a library for building stateful, multi-actor applications. This allows for defining clear, manageable workflows as graphs of nodes (processing steps) and edges (transitions).
  - Agents interact with utilities for tasks like database access, LLM calls, etc.
- **Utilities (`src/logllm/utils/`)**:
  - `database.py`: `ElasticsearchDatabase` class for all Elasticsearch interactions.
  - `llm_model.py`: `GeminiModel` class for interfacing with Google's Gemini LLMs. Includes rate limiting, structured output, and embedding generation.
  - `local_embedder.py`: `LocalSentenceTransformerEmbedder` for generating text embeddings locally.
  - `prompts_manager.py`: `PromptsManager` class for managing LLM prompt templates stored in JSON files, with Git-based version control.
  - `collector.py`: `Collector` class for discovering, grouping, and ingesting log files.
  - `container_manager.py`: `DockerManager` for managing Docker containers (Elasticsearch, Kibana).
  - `logger.py`: Singleton `Logger` class for standardized application logging.
  - Other utilities like `data_struct.py` and `chunk_manager.py`.
- **API (`src/logllm/api/`)**:
  - A **FastAPI** application providing HTTP endpoints.
  - Mirrors many functionalities of the CLI, allowing for UI interaction and external service integration.
  - Uses Pydantic models for request/response validation and serialization.
- **Configuration (`src/logllm/config/config.py`)**:
  - Centralized Python file for all application settings (database URLs, model names, default paths, agent parameters).

### 2.2 Frontend (React/TypeScript)

- **Location**: `frontend/` directory.
- **Technology**: Built with React, TypeScript, and Material UI (MUI) for components and styling. Vite is used as the build tool.
- **Structure**:
  - `pages/`: Components representing distinct views/features of the application.
  - `components/`: Reusable UI elements (e.g., `Sidebar`).
  - `services/`: Modules for making API calls to the backend.
  - `layouts/`: Defines the main application layout (e.g., `MainLayout` with AppBar and Sidebar).
  - `routes/`: Client-side routing configuration using `react-router-dom`.
  - `theme/`: Custom MUI theme definitions (including light/dark mode).
  - `types/`: TypeScript interfaces, often mirroring backend Pydantic models.

### 2.3 Database

- **Elasticsearch**: Used as the primary data store for:
  - Raw log lines.
  - Parsed (structured) log data.
  - Log group metadata.
  - Parsing status and history.
  - Generated error summaries.
  - Vector embeddings (for RAG, if implemented).
- **Kibana**: Used for visualization and exploration of data stored in Elasticsearch.

### 2.4 Containerization

- **Docker**: Elasticsearch and Kibana are run as Docker containers, managed by the `DockerManager` utility and the `db` CLI command.

## 3. Development Environment Setup

### 3.1 Prerequisites

- **Python**: Version 3.11 or higher.
- **Node.js & npm/yarn**: Latest LTS version recommended (for frontend development).
- **Docker**: Docker Desktop (Windows/Mac) or Docker Engine (Linux) must be installed and running.
- **Git**: For version control.
- **Google Generative AI API Key**: Required for interacting with Gemini models. Set this as an environment variable: `GENAI_API_KEY`.

### 3.2 Cloning the Repository

```bash
git clone <repository_url>
cd LogLLM
```

### 3.3 Backend Setup

1.  **Create and Activate a Python Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # venv\Scripts\activate    # On Windows
    ```
2.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set Environment Variables**:
    - Ensure `GENAI_API_KEY` is set in your environment. You can add it to a `.env` file at the project root (and ensure `.env` is in `.gitignore`) and use a library like `python-dotenv` if preferred, or set it directly in your shell.
    ```bash
    export GENAI_API_KEY="YOUR_API_KEY_HERE" # Example for Linux/macOS
    ```

### 3.4 Frontend Setup

1.  **Navigate to the frontend directory**:
    ```bash
    cd frontend
    ```
2.  **Install JavaScript Dependencies**:
    ```bash
    npm install
    # OR
    # yarn install
    ```
3.  **Environment Variables (Frontend)**:
    - The frontend uses Vite, which supports `.env` files in the `frontend/` directory (e.g., `frontend/.env`).
    - The primary variable is `VITE_API_BASE_URL`, which should point to your backend API (e.g., `VITE_API_BASE_URL=http://localhost:8000/api`). A default is provided in `frontend/src/services/api.ts`.

### 3.5 Running Backend Services (Elasticsearch & Kibana)

From the project root directory:

```bash
python -m src.logllm db start
```

This command will:

- Check if Docker is running.
- Start Colima (on macOS, if configured and not running).
- Create a Docker network (`movelook_network`) and volume (`movelook_volume`) if they don't exist.
- Pull Elasticsearch and Kibana images if not present.
- Start the Elasticsearch and Kibana containers.

Verify services are running:

- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`
- CLI check: `python -m src.logllm db status`

## 4. Running the Application

### 4.1 Backend FastAPI Server

From the project root directory:

```bash
uvicorn src.logllm.api.main:app --reload --port 8000
```

- `--reload`: Enables auto-reloading on code changes.
- `--port 8000`: Specifies the port (default for frontend API calls).
  The API will be accessible at `http://localhost:8000`. Swagger UI documentation at `http://localhost:8000/docs`.

### 4.2 Frontend Development Server

From the `frontend/` directory:

```bash
npm run dev
# OR
# yarn dev
```

This will typically start the frontend application on `http://localhost:5173` (Vite's default).

### 4.3 Using the CLI

From the project root directory (with your Python virtual environment activated):

```bash
python -m src.logllm --help # Shows top-level commands
python -m src.logllm <command> --help # Shows help for a specific command
```

Example:

```bash
python -m src.logllm collect -d ./path/to/your/logs
python -m src.logllm static-grok-parse run --all-groups --grok-patterns-file ./grok_patterns.yaml
```

## 5. Project Structure Deep Dive

- **`src/logllm/`**: Main backend Python package.

  - **`cli/`**:
    - `__main__.py`: Main argument parser and entry point for CLI commands.
    - `analyze_errors.py`, `collect.py`, `container.py`, `normalize_ts.py`, `pm.py`, `static_grok_parse.py`: Individual CLI command handlers.
  - **`agents/`**: Core processing logic.
    - `agent_abc.py`: Abstract base class for LangGraph agents.
    - `error_summarizer/`: LangGraph agent for error summarization pipeline.
      - `__init__.py`: Agent definition.
      - `api/`: Services used by the agent (ES, LLM, Clustering, Sampling).
      - `states.py`: TypedDict state definition for the agent.
      - `__main__.py`: Example runner for this agent.
    - `static_grok_parser/`: LangGraph agent for static Grok parsing.
    - `timestamp_normalizer/`: LangGraph agent for timestamp normalization.
    - `parser_agent.py`: Older agents for filesystem-based parsing (`SimpleGrokLogParserAgent`, `GroupLogParserAgent`). (Less emphasis now).
    - `es_parser_agent.py`: Older LangGraph agents for ES-based parsing with LLM pattern generation. (Superseded by `static_grok_parser` for static patterns).
  - **`utils/`**: Shared utility classes.
    - `database.py`: `ElasticsearchDatabase` class.
    - `llm_model.py`: `LLMModel` ABC and `GeminiModel` implementation.
    - `local_embedder.py`: `LocalSentenceTransformerEmbedder` implementation.
    - `prompts_manager.py`: `PromptsManager` for LLM prompts.
    - `collector.py`: `Collector` for log ingestion.
    - `container_manager.py`: `DockerManager` for ES/Kibana.
    - `logger.py`: `Logger` singleton.
    - `data_struct.py`: Dataclasses for log file/line representation.
  - **`api/`**: FastAPI application.
    - `main.py`: FastAPI app instantiation, middleware, root endpoints.
    - `routers/`: API routers for different features (e.g., `collect_router.py`, `container_router.py`).
    - `models/`: Pydantic models for API request/response validation.
  - **`config/config.py`**: Centralized configuration settings.
  - **`data_schemas/`**: Older Pydantic models (some specific agent states are now in `agents/<agent_name>/states.py`).

- **`frontend/`**: React/TypeScript frontend application.

  - `public/`: Static assets.
  - `src/`:
    - `App.tsx`: Root React component.
    - `main.tsx`: Application entry point.
    - `components/`: Reusable UI components (e.g., `sidebar/Sidebar.tsx`).
    - `pages/`: Top-level page components (e.g., `CollectPage.tsx`, `AnalyzeErrorsPage.tsx`).
    - `services/`: Modules for making API calls to the backend (e.g., `collectService.ts`).
    - `layouts/`: Main application layout components (e.g., `MainLayout.tsx`).
    - `routes/`: Client-side routing (`AppRoutes.tsx`).
    - `theme/`: Material UI custom theming (`theme.ts`, `CustomThemeProvider.tsx`).
    - `types/`: TypeScript interface definitions.
    - `index.css`, `App.css`: Global and App-level styles.

- **`prompts/`**: Default directory for LLM prompt JSON files.
  - `prompts.json`: Main prompt file.
  - `test.json`: Test prompt file (used with CLI `--test` flag).
- **`grok_patterns.yaml`**: Example/default YAML file for defining Grok patterns for the `static-grok-parse` command.
- **`docs/`**: Project documentation.
- **`requirements.txt`**: Python backend dependencies.
- **`.env.example`**: Example for environment variables (e.g., `GENAI_API_KEY`).
- **`Dockerfile`**, **`docker-compose.yml`** (if present, for custom application containerization, not just ES/Kibana).

## 6. Key Workflows and How to Contribute

### 6.1 Log Collection (`Collector`, `collect` CLI)

- **Existing Logic**: `utils/collector.py` scans directories, identifies groups, and ingests lines into ES, tracking progress in `log_last_line_status`.
- **Contribution Areas**:
  - Supporting new log file types or compression formats.
  - Improving efficiency of file scanning or line reading.
  - Enhancing group identification logic.
  - Modifying the structure of documents stored in `group_infos` or `log_<group_name>`.

### 6.2 Static Grok Parsing (`StaticGrokParserAgent`, `static-grok-parse` CLI)

- **Existing Logic**: Reads `grok_patterns.yaml`, processes log groups from ES, applies patterns, handles derived fields, and stores results in `parsed_log_<group>` / `unparsed_log_<group>`. Status in `static_grok_parse_status`.
- **Services Used**: `GrokPatternService`, `GrokParsingService`, `DerivedFieldProcessor`, `ElasticsearchDataService` (within the agent's `api` submodule).
- **Contribution Areas**:
  - **Defining Grok Patterns**: The primary way to customize parsing is by editing `grok_patterns.yaml` (or a custom YAML specified via CLI). Add new group sections, define `grok_pattern` and `derived_fields`.
  - **Improving `DerivedFieldProcessor`**: Add more complex derived field logic if needed.
  - **Agent Workflow**: Modifying the LangGraph flow in `StaticGrokParserAgent` for different error handling or steps.
  - **Performance**: Optimizing ES queries or bulk indexing in `ElasticsearchDataService`.

### 6.3 Timestamp Normalization (`TimestampNormalizerAgent`, `normalize-ts` CLI)

- **Existing Logic**: LangGraph agent processes `parsed_log_<group>` indices, using `TimestampNormalizationService` to parse various timestamp formats and update `@timestamp` in-place.
- **Contribution Areas**:
  - **Enhancing `TimestampNormalizationService`**: Add support for more exotic timestamp formats or improve heuristics for ambiguous ones.
  - **Agent Workflow**: Modify the LangGraph flow for error handling or batching strategies.
  - **Performance**: Optimize ES scroll/update operations in `TimestampESDataService`.

### 6.4 Error Summarization (`ErrorSummarizerAgent`, `analyze-errors` CLI)

- **Existing Logic**: LangGraph agent fetches errors, embeds messages (local or API), clusters (DBSCAN), samples, generates structured summaries with LLM (`LLMService`), and stores them.
- **Services Used**: `ErrorSummarizerESDataService`, `LogClusteringService`, `LogSamplingService`, `LLMService`.
- **Contribution Areas**:
  - **Embedding Strategy**: Experiment with different `embedding_model_name` values (local Sentence Transformers or Google API models).
  - **Clustering Parameters**: Tune `dbscan_eps` and `dbscan_min_samples` for better cluster quality.
  - **Sampling Logic**: Modify `LogSamplingService` for different sampling strategies.
  - **Prompt Engineering**: Refine prompts used by `LLMService` (via `PromptsManager`) for `LogClusterSummaryOutput` to improve summary quality, cause analysis, or keyword generation.
  - **LLM Choice**: Change the `llm_model_for_summary`.
  - **Agent Workflow**: Adjust the LangGraph flow, e.g., add more sophisticated pre/post-processing for summaries.

### 6.5 Prompt Management (`PromptsManager`, `pm` CLI)

- **Existing Logic**: `utils/prompts_manager.py` handles JSON storage and Git versioning. `cli/pm.py` provides user interface.
- **Contribution Areas**:
  - Adding new prompts for new LLM-driven features.
  - Refining existing prompts for clarity or better LLM performance.
  - Extending `PromptsManager` capabilities if needed (e.g., support for different storage backends, though Git is core).

### 6.6 API Development (FastAPI)

- **Location**: `src/logllm/api/`
- **Process**:
  1.  Define Pydantic models for request/response in `src/logllm/api/models/`.
  2.  Create or update a router in `src/logllm/api/routers/`.
  3.  Implement the endpoint logic, often by calling the relevant Agent's `run` method or utility functions.
  4.  For long-running tasks, implement background tasking (e.g., using FastAPI's `BackgroundTasks` or Celery) and provide status endpoints (see `analyze_errors_router.py` or `static_grok_parse_router.py` for examples).
  5.  Register the router in `src/logllm/api/main.py`.
  6.  Add corresponding service functions in `frontend/src/services/`.

### 6.7 Frontend Development (React/TypeScript)

- **Location**: `frontend/`
- **Process**:
  1.  Define necessary TypeScript types in `frontend/src/types/` (often mirroring backend Pydantic models).
  2.  Create service functions in `frontend/src/services/` to call new API endpoints.
  3.  Develop new page components in `frontend/src/pages/` or reusable components in `frontend/src/components/`.
  4.  Use Material UI for UI elements and adhere to the existing theming.
  5.  Manage state using React hooks (`useState`, `useEffect`, `useCallback`, `useContext`).
  6.  Add new routes in `frontend/src/routes/AppRoutes.tsx`.
  7.  Update sidebar in `frontend/src/components/sidebar/Sidebar.tsx` if it's a main feature.

## 7. Coding Conventions & Best Practices

- **Python (Backend)**:
  - Follow **PEP 8** style guidelines. Use a linter/formatter like Black or Flake8.
  - Use **type hinting** extensively.
  - Write clear and concise **docstrings** for modules, classes, and functions (Google style or reStructuredText).
  - For complex agent workflows, prefer **LangGraph** for clarity and state management.
  - Manage external dependencies in `requirements.txt`.
  - Use the shared `Logger` from `src/logllm/utils/logger.py` for all logging.
  - Centralize configurable parameters in `src/logllm/config/config.py`.
- **TypeScript/React (Frontend)**:
  - Follow standard React best practices (e.g., component composition, hook usage).
  - Maintain a consistent code style (ESLint/Prettier are recommended).
  - Define clear `props` interfaces for components.
  - Organize files logically within `pages`, `components`, `services`, `types`.
- **Git Version Control**:
  - Use feature branches for new development or bug fixes (`git checkout -b feature/my-new-feature`).
  - Write clear, concise, and imperative Git commit messages. Reference issue numbers if applicable.
  - Keep commits small and focused.
  - Submit Pull Requests (PRs) for review before merging to main branches.
- **Error Handling**:
  - Implement robust error handling in both backend (API, agents) and frontend (service calls, UI feedback).
  - Provide informative error messages to the user/logger.
- **Security**:
  - Be mindful of security implications, especially when handling file paths, executing external commands, or processing user inputs.
  - The default Elasticsearch setup disables security; for production, this must be enabled and properly configured.

## 8. Testing

_(While no specific test files were provided in the input, this section outlines general expectations.)_

- **Unit Tests**:
  - Python: Use `unittest` or `pytest` to test individual functions and methods, especially in utility classes and agent services (e.g., `TimestampNormalizationService`, `GrokPatternService`). Mock external dependencies like LLM calls or DB interactions where appropriate.
  - TypeScript: Use Jest or Vitest with React Testing Library to test individual React components and service functions.
- **Integration Tests**:
  - Test the interaction between components, e.g., an agent's full LangGraph workflow, or an API endpoint calling an agent.
  - May involve setting up a test Elasticsearch instance.
- **End-to-End (E2E) Tests**:
  - CLI: Write shell scripts or use Python's `subprocess` to test full CLI command workflows.
  - Frontend: Use tools like Cypress or Playwright to test user interaction flows through the web UI.

## 9. Future Direction: Modern Context Protocol (MCP)

As `logLLM` evolves, a key direction for enhancing inter-module communication and LLM interaction is the adoption of a **Modern Context Protocol (MCP)**.

### 9.1 What is MCP (Conceptual)?

MCP, in the context of `logLLM`, would be a standardized, rich, and evolving specification for how different components (agents, utilities, services) exchange contextual information. This goes beyond simple JSON data transfer and aims to create a more semantically aware "fabric" for data flow.

**Key characteristics of MCP could include:**

- **Structured Data Payloads**: Clearly defined schemas (e.g., using Pydantic on the backend, corresponding TypeScript interfaces on the frontend) for context objects.
- **Semantic Tagging**: Metadata indicating the type, source, and significance of contextual information.
- **Context Propagation**: Mechanisms for automatically or intelligently passing relevant context through complex workflows (e.g., in LangGraph agents).
- **Event-Driven Capabilities**: Potential for components to publish and subscribe to context updates.
- **Versioning**: As context needs evolve, MCP schemas would be versioned.
- **Extensibility**: Designed to allow new types of context to be easily added.

### 9.2 Why MCP for `logLLM`?

- **Richer LLM Interactions**: Provide LLMs with more nuanced and comprehensive context, leading to better quality outputs (e.g., more accurate Grok patterns, more insightful error summaries). Instead of just passing log lines, pass structured log objects with metadata, links to related logs, or previous analysis results.
- **Improved Agent Interoperability**: Standardize how agents share information, reducing boilerplate conversion code and making it easier to chain agents or build more complex pipelines.
- **Enhanced Debuggability and Observability**: A clear context protocol makes it easier to trace data flow and understand the state of the system at any point.
- **Facilitate Advanced Features**:
  - **Multi-modal context**: Incorporating (e.g.) metrics or traces alongside logs.
  - **User feedback loops**: Standardizing how user feedback (e.g., on summary quality) is captured and fed back as context.
  - **Proactive analysis**: Enabling agents to react to specific contextual events.

### 9.3 Developing with MCP in Mind

When developing new features or refactoring existing ones, consider:

1.  **Identify Contextual Needs**: What information does this component _need_ to perform its task effectively? What information does it _produce_ that could be valuable context for other components?
2.  **Define Context Schemas**:
    - If passing new types of structured data, define Pydantic models for it.
    - Think about how this schema might be represented in TypeScript for the frontend.
3.  **LangGraph State**: For agents using LangGraph, the agent's `TypedDict` state is a primary candidate for MCP integration. Design state fields to hold rich context objects rather than just primitive types.
4.  **API Design**: API endpoints (FastAPI) should accept and return data that aligns with MCP schemas where appropriate.
5.  **Prompt Engineering**: Prompts for LLMs should be designed to leverage the richer context provided by MCP. This might involve new placeholders or instructions on how to interpret structured context.
6.  **Data Flow**: Consider how context should flow. For example, in the Error Summarizer, the context from log fetching (e.g., query parameters) and clustering (e.g., cluster ID, member count) should be passed cleanly to the summarization step.

### 9.4 Potential MCP Integration Points in `logLLM`

- **Error Summarization Pipeline**:
  - Pass detailed cluster information (not just sample logs, but also cluster statistics, embedding vectors if useful) as MCP objects.
  - The output `LogClusterSummaryOutput` is already a good step towards structured MCP.
- **Static Grok Parsing**:
  - Context about the log group (e.g., typical fields, previously successful patterns for similar groups) could be passed as MCP to a (hypothetical future) LLM-assisted pattern refinement step.
- **Cross-Workflow Context**:
  - Information from `collect` (e.g., file types, sizes within a group) could be MCP context for `static-grok-parse`.
  - Summaries from `analyze-errors` could become MCP context for future root cause analysis agents.

Adopting an MCP mindset will help build a more intelligent, interconnected, and maintainable `logLLM` system.

## 10. Troubleshooting Common Issues

- **Docker Connection Issues**: Ensure Docker Desktop/Engine is running. On macOS, check Colima status (`colima status`). If `DOCKER_HOST` issues arise, ensure Colima's environment variables are sourced or Docker Desktop is configured correctly.
- **Elasticsearch/Kibana Not Starting**:
  - Check container logs: `docker logs movelook_elastic_search` / `docker logs movelook_kibana`.
  - Ensure ports 9200 and 5601 are not already in use by other applications.
  - Check Docker volume permissions if ES fails to write data.
- **`GENAI_API_KEY` Not Found**: Ensure the environment variable is correctly set and accessible by the Python process.
- **Python Dependencies**: If `ModuleNotFoundError` occurs, ensure your virtual environment is activated and `pip install -r requirements.txt` was successful.
- **Frontend Fails to Connect to API**:
  - Verify the backend API server (`uvicorn ...`) is running.
  - Check the `VITE_API_BASE_URL` in `frontend/.env` (or the default in `api.ts`) and ensure it matches the backend's host and port.
  - Check browser console for CORS errors or network request failures.
- **Grok Parsing Failures**:
  - Double-check the syntax in your `grok_patterns.yaml`.
  - Use the `static-grok-parse list` CLI command to inspect parsing statuses and identify problematic files or patterns.
  - Examine logs in `unparsed_log_<group_name>` for clues.
- **LLM Issues (e.g., empty responses, errors)**:
  - Check `logLLM`'s own logs (e.g., `movelook.log`) for detailed error messages from `GeminiModel`.
  - Verify your `GENAI_API_KEY` has access to the requested models.
  - Check for rate limiting (though `GeminiModel` has internal handling).
  - Review prompts for clarity and ensure they align with the LLM's capabilities and any specified output schemas.

## 11. Further Resources

- This `docs/` directory.
- Material UI Documentation: [https://mui.com/](https://mui.com/)
- React Documentation: [https://react.dev/](https://react.dev/)
- FastAPI Documentation: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- LangGraph Documentation: [https://python.langchain.com/docs/langgraph/](https://python.langchain.com/docs/langgraph/)
- Google Generative AI (Gemini) Documentation: [https://ai.google.dev/docs](https://ai.google.dev/docs)
- Elasticsearch Python Client Documentation: [https://elasticsearch-py.readthedocs.io/](https://elasticsearch-py.readthedocs.io/)

# LogLLM Development: Quick Start Guide

This guide provides a brief overview to get you started.

## Project Goal

`logLLM` aims to provide a comprehensive suite of tools for advanced log analysis and management, leveraging Large Language Models (LLMs) for tasks like parsing, error summarization, and pattern recognition.

## Core Components

1.  **Backend (Python)**:

    - **CLI (`src/logllm/cli`)**: Main user interface for orchestrating tasks.
    - **Agents (`src/logllm/agents`)**: Perform core processing logic (e.g., log parsing, error summarization). Many use `LangGraph` for complex workflows.
    - **Utilities (`src/logllm/utils`)**: Support modules for database interaction (Elasticsearch), LLM communication (Gemini), prompt management, container management, etc.
    - **API (`src/logllm/api`)**: FastAPI application providing HTTP endpoints for frontend interaction.
    - **Configuration (`src/logllm/config`)**: Centralized settings.

2.  **Frontend (React/TypeScript)**:

    - **UI (`frontend/`)**: Web interface built with React, TypeScript, and Material UI to interact with the API.

3.  **Services**:
    - **Elasticsearch & Kibana**: Managed via Docker for log storage, indexing, and visualization.

## Key Workflows

- **Log Collection**: `Collector` ingests logs into Elasticsearch.
- **Static Grok Parsing**: `StaticGrokParserAgent` parses logs in ES using YAML-defined Grok patterns.
- **Timestamp Normalization**: `TimestampNormalizerAgent` standardizes timestamps in parsed logs.
- **Error Summarization**: `ErrorSummarizerAgent` fetches, embeds, clusters, and summarizes error logs using LLMs.
- **Prompt Management**: `PromptsManager` and `pm` CLI manage LLM prompts with Git versioning.

## Technology Stack Highlights

- **Backend**: Python 3.11+, FastAPI, LangGraph, Pydantic, `google-generativeai`, `elasticsearch-py`.
- **Frontend**: React, TypeScript, Material UI, Vite.
- **Database**: Elasticsearch.
- **Containerization**: Docker.
- **Version Control**: Git.

## Getting Started

1.  **Prerequisites**: Python 3.11+, Node.js (for frontend), Docker, Git.
2.  **Clone Repository**: `git clone <repository_url>`
3.  **Backend Setup**:
    - Create a Python virtual environment and activate it.
    - Install dependencies: `pip install -r requirements.txt`
    - Set `GENAI_API_KEY` environment variable for Google Gemini access.
4.  **Frontend Setup** (in `frontend/` directory):
    - Install dependencies: `npm install` (or `yarn install`).
5.  **Start Backend Services**:
    - Run `python -m src.logllm db start` to launch Elasticsearch and Kibana in Docker.
6.  **Run Application**:
    - **Backend API**: `uvicorn src.logllm.api.main:app --reload --port 8000` (from project root).
    - **Frontend Dev Server**: `cd frontend && npm run dev` (or `yarn dev`).
    - **CLI**: `python -m src.logllm <command> --help` (from project root).

## Key Directories

- `src/logllm/`: Main backend Python code.
- `frontend/`: React frontend code.
- `prompts/`: Default location for LLM prompt JSON files.
- `grok_patterns.yaml`: Example file for static Grok patterns.
- `docs/`: Project documentation (you are here!).

## Contribution Flow

1.  Create a feature branch from `main`
2.  Implement your changes.
3.  Write/update documentation and tests (if applicable).
4.  Ensure code adheres to project conventions (PEP 8 for Python).

**For more detailed information, please refer to the [Detailed Development Guideline](./DETAILED_GUIDELINE.md).**

# LogLLM Web UI Documentation

Welcome to the documentation for the `logLLM` web user interface. This frontend application provides a graphical way to interact with the `logLLM` backend API, enabling users to manage services, collect and parse logs, normalize timestamps, analyze errors, and more.

## Overview

The frontend is built using modern web technologies:

- **React**: A JavaScript library for building user interfaces.
- **TypeScript**: A superset of JavaScript that adds static typing.
- **Material UI (MUI)**: A popular React UI framework providing pre-built components and theming capabilities.
- **Vite**: A fast frontend build tool.
- **React Router**: For client-side routing and navigation.

## Key Features

- **Modular Design**: Components, pages, services, and types are organized into logical directories.
- **Responsive Layout**: Uses Material UI's grid and layout components.
- **Theming**: Supports light and dark modes via `CustomThemeProvider`.
- **API Interaction**: Communicates with the `logLLM` backend API (FastAPI) through dedicated service modules.
- **Task Management**: Several pages implement polling mechanisms to track the status of long-running backend tasks.
- **Local Storage Persistence**: User preferences and some form inputs are persisted in local storage to improve user experience across sessions.

## Navigating This Documentation

This documentation is structured to mirror the frontend application's codebase:

- **[Setup & Core](./setup.md)**: Information on the application entry point, global styles, and root component.
- **[Routing](./routing.md)**: How navigation and page mapping are handled.
- **[Layouts](./layouts.md)**: The main application layout structure.
- **[Theming](./theming.md)**: Details on the custom theme and theme switching.
- **[Components](./components/README.md)**: Documentation for reusable UI components (e.g., Sidebar).
- **[Pages](./pages/README.md)**: Detailed descriptions of each page/view in the application.
- **[Services](./services/README.md)**: How the frontend interacts with the backend API.
- **[Types](./types.md)**: Overview of TypeScript types used, especially those mirroring backend models.

This documentation aims to provide a clear understanding of the frontend's architecture, components, and interaction patterns.

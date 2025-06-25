# Frontend Setup and Core Files

This section describes the initial setup and core files of the `logLLM` frontend application.

## 1. Entry Point (`frontend/src/main.tsx`)

- **File**: `frontend/src/main.tsx`
- **Purpose**: This is the main entry point of the React application.
- **Key Actions**:
  - Imports `StrictMode` from React for highlighting potential problems in an application.
  - Imports `createRoot` from `react-dom/client` for the new React 18 root API.
  - Imports the global CSS file (`./index.css`).
  - Imports the main application component (`App` from `./App.tsx`).
  - Uses `createRoot` to get a handle to the DOM element with `id="root"` (typically in `index.html`).
  - Renders the `<App />` component wrapped in `<StrictMode>` into the root DOM element.

## 2. Root Application Component (`frontend/src/App.tsx`)

- **File**: `frontend/src/App.tsx`
- **Purpose**: This is the root component of the application.
- **Key Features**:
  - Sets up the `BrowserRouter` from `react-router-dom` to enable client-side routing.
  - Wraps the entire application with `CustomThemeProvider` (from `./theme/CustomThemeProvider`) to provide theme context (light/dark mode) and MUI theme overrides to all child components.
  - Renders `AppRoutes` (from `./routes/AppRoutes`), which defines all the application's routes and their corresponding page components.

## 3. Global Styles

### `frontend/src/index.css`

- **Purpose**: Contains global CSS styles and resets.
- **Key Styles**:
  - Root variables for font family, line height, color scheme, text color, and background color (supporting light/dark modes via `@media (prefers-color-scheme: light)`).
  - Basic styles for links (`<a>`), body, headings (`<h1>`), and buttons (`<button>`).
  - Ensures the application takes up the full viewport height (`min-height: 100vh`).

### `frontend/src/App.css`

- **Purpose**: Contains styles specific to the `App` component or overall application layout elements that might not fit into MUI's styling system directly.
- **Key Styles (as provided)**:
  - Styling for `#root` element (max-width, margin, padding).
  - Styling for `.logo` elements (height, padding, hover effects, animations).
  - Example animation (`logo-spin`).
  - Styling for a `.card` class (padding).
  - Styling for `.read-the-docs` class.
  - **Note**: Some of these styles might be examples or remnants from a template and may or may not be actively used by the current MUI-based components. The primary styling is driven by Material UI and the custom theme.

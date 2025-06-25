# Frontend Layouts (`MainLayout.tsx`)

## File: `frontend/src/layouts/MainLayout.tsx`

### Overview

The `MainLayout.tsx` component defines the primary structural layout for most pages in the `logLLM` web application. It provides a consistent frame including a top AppBar (navigation bar) and a collapsible Sidebar for navigation. Routed page content is rendered within this main layout.

### Key Features

- **Persistent Structure**: Ensures a common look and feel across different views.
- **Top AppBar**:
  - Displays the application title ("LogLLM Dashboard").
  - Contains an icon button (`<MenuIcon />`) to toggle the visibility/state of the Sidebar.
  - Includes a theme toggle button (`<Brightness4Icon />` / `<Brightness7Icon />`) to switch between light and dark modes.
- **Collapsible Sidebar**:
  - Uses the `Sidebar` component (`../components/sidebar/Sidebar`).
  - Its open/closed state is managed by the `open` state variable within `MainLayout`.
  - The `handleDrawerToggle`, `handleDrawerOpen`, and `handleDrawerClose` functions control the sidebar's state.
- **Content Area**:
  - Uses Material UI's `<Box component="main">` to define the main content area.
  - Includes a `<Toolbar />` component for proper spacing below the fixed AppBar.
  - Renders the page-specific content via `<Outlet />` from `react-router-dom`.

### Component Structure

- **Imports**:

  - `React`, `useState` for state management.
  - `Outlet` from `react-router-dom` for rendering nested route components.
  - Material UI components: `Box`, `AppBar`, `Toolbar`, `IconButton`, `Typography`, `CssBaseline`.
  - Material UI icons: `MenuIcon`, `Brightness4Icon`, `Brightness7Icon`.
  - `Sidebar` component.
  - `ThemeContext` from `../theme/CustomThemeProvider` to access theme mode and toggle function.

- **State**:

  - `open` (boolean): Controls whether the `Sidebar` is in its expanded or collapsed state. Initialized to `true` (sidebar starts open).

- **Event Handlers**:

  - `handleDrawerOpen()`: Sets `open` to `true`.
  - `handleDrawerClose()`: Sets `open` to `false`.
  - `handleDrawerToggle()`: Toggles the `open` state. This is typically connected to the main menu icon in the AppBar.

- **Rendering**:
  - A root `<Box sx={{ display: 'flex' }}>` establishes a flex container for the AppBar, Sidebar, and main content.
  - `<CssBaseline />` provides MUI's baseline CSS normalizations.
  - `<AppBar>`:
    - Fixed position.
    - Contains `<Toolbar>` with the menu icon, title, and theme toggle icon.
  - `<Sidebar>`:
    - Receives `open`, `handleDrawerClose`, and `handleDrawerOpen` props to manage its state and behavior.
  - `<Box component="main">`:
    - Takes up the remaining space (`flexGrow: 1`).
    - Padded (`p: 3`).
    - Renders `<Toolbar />` for spacing.
    - Renders `<Outlet />`, which is where the content of the currently active route (e.g., `DashboardPage`, `CollectPage`) will be displayed.

### Interaction

- The user can click the `<MenuIcon />` in the AppBar to open or close the `Sidebar`.
- The user can click the theme toggle icon in the AppBar to switch between light and dark modes.
- The main content of the application changes based on the current route, rendered via the `<Outlet />`.

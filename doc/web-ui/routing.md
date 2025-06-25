# Frontend Routing (`AppRoutes.tsx`)

## File: `frontend/src/routes/AppRoutes.tsx`

### Overview

The `AppRoutes.tsx` file is responsible for defining the application's routing structure. It uses `react-router-dom` to map URL paths to specific page components. All defined routes are nested within the `MainLayout` component, meaning that pages like the Dashboard, Container Management, etc., will share the common layout (AppBar, Sidebar).

### Structure

- **Imports**:

  - `React` for component definition.
  - `Routes` and `Route` components from `react-router-dom`.
  - `MainLayout` component from `../layouts/MainLayout`.
  - All page components (e.g., `DashboardPage`, `ContainerPage`, etc.) from the `../pages/` directory.

- **`AppRoutes` Component**:
  - A functional React component.
  - Returns a `<Routes>` block which contains individual `<Route>` definitions.
  - **Layout Wrapping**: The top-level `<Route>` uses `element={<MainLayout />}`. This means `MainLayout` will be rendered, and any nested routes will render their `element` inside `MainLayout`'s `<Outlet />` component.
  - **Page Routes**:
    - Each subsequent `<Route>` defines a path and the page component to render for that path.
    - Example: `<Route path="/" element={<DashboardPage />} />` maps the root URL to the `DashboardPage`.
    - Example: `<Route path="/container" element={<ContainerPage />} />` maps `/container` to the `ContainerPage`.
  - **Catch-all Route (404)**:
    - A route with `path="*"` is used to render the `NotFoundPage` for any URL that doesn't match the other defined routes.

### Defined Routes

The following routes are defined:

- `/` (Root): Renders `DashboardPage`.
- `/analyze-errors`: Renders `AnalyzeErrorsPage`.
- `/collect`: Renders `CollectPage`.
- `/container`: Renders `ContainerPage`.
- `/groups`: Renders `GroupInfoPage`.
- `/static-grok-parser`: Renders `StaticGrokParserPage`.
- `/normalize-ts`: Renders `NormalizeTsPage`.
- `*` (Catch-all): Renders `NotFoundPage`.

### How it Works

1.  When the application loads or the URL changes, `react-router-dom` matches the current URL against the defined routes.
2.  The `MainLayout` component is always rendered because it's the element for the parent route.
3.  The specific page component corresponding to the matched nested route (e.g., `DashboardPage` for `/`) is then rendered within the `<Outlet />` placeholder inside `MainLayout`.
4.  If no specific route matches, the `NotFoundPage` is rendered.

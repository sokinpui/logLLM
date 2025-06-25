# Not Found Page (`NotFoundPage.tsx`)

## File: `frontend/src/pages/NotFoundPage.tsx`

### Overview

The `NotFoundPage` component is a simple fallback page displayed when a user navig انرژیates to a URL that does not match any of the defined routes in the application.

### Purpose

- To inform the user that the requested page could not be found.
- To provide a clear way for the user to return to a valid part of the application, typically the dashboard or home page.

### Structure

- **Imports**:

  - `React` from 'react'.
  - `Typography`, `Paper`, and `Button` from `@mui/material` for styling and UI elements.
  - `Link` from `react-router-dom` to enable client-side navigation.

- **Rendering**:
  - A `Paper` component acts as a container with padding and centered text.
  - A `Typography` component with `variant="h3"` displays the "404 - Page Not Found" message.
  - Another `Typography` component with `variant="body1"` provides a brief explanation.
  - A Material UI `Button` is rendered:
    - It's styled with `variant="contained"`.
    - It uses `component={Link}` and `to="/"` to navigate the user back to the Dashboard page when clicked.
    - The button text is "Go to Dashboard".

### Behavior

- This page is rendered by the catch-all route (`<Route path="*" ... />`) defined in `frontend/src/routes/AppRoutes.tsx`.
- It's a static page with no complex logic or state management.

# Sidebar Component

## File: `frontend/src/components/sidebar/Sidebar.tsx`

### Overview

The `Sidebar` component is a persistent, collapsible navigation drawer used in the `MainLayout`. It provides links to the different pages of the `logLLM` application.

### Key Features

- **Collapsible**: Can be opened (wide, showing icons and text) or closed (narrow, showing only icons).
- **Navigation**: Uses `ListItemButton` components from Material UI, wrapped with `Link` from `react-router-dom` for client-side navigation.
- **Active State Indication**: Highlights the currently active sidebar item based on the browser's current URL path (`useLocation` hook).
- **Icons**: Each navigation item has an associated Material UI icon.
- **Tooltips**: When collapsed, tooltips show the item text on hover.
- **Styled Components**: Uses MUI's `styled` utility for custom styling of the drawer and its header, including transition effects for opening and closing.

### Structure and Props

- **`sidebarItems: SidebarItem[]` Array**:

  - Defines the content of the sidebar. Each object in the array represents a navigation item and has the following properties:
    - `text` (string): The text label for the item.
    - `icon` (React.ReactElement): The icon component for the item.
    - `path` (string): The URL path the item links to.
    - `divider` (boolean, optional): If `true`, a `Divider` is rendered after this item.

- **`SidebarProps` Interface**:

  - `open` (boolean): Controls whether the sidebar is open or closed. Passed from `MainLayout`.
  - `handleDrawerClose` (function): Callback function to close the sidebar. Passed from `MainLayout`.
  - `handleDrawerOpen` (function): Callback function to open the sidebar. Passed from `MainLayout`.

- **Styled Components**:
  - `StyledDrawer`: A custom `Drawer` component styled for open/closed states and transitions.
  - `DrawerHeader`: A styled `div` for the header section of the drawer, typically containing the toggle button.
  - `openedMixin`, `closedMixin`: Helper functions defining the CSS-in-JS styles for the open and closed states of the drawer.

### Rendering and Logic

- The `Sidebar` component receives its `open` state and control functions (`handleDrawerClose`, `handleDrawerOpen`) as props from `MainLayout`.
- The `DrawerHeader` contains an `IconButton` with either `<ChevronLeftIcon />` or `<ChevronRightIcon />` to toggle the sidebar's `open` state by calling `handleDrawerOpen` or `handleDrawerClose`.
- It maps over the `sidebarItems` array to render each navigation item:
  - Each item is wrapped in a `<Tooltip>` that only shows when the sidebar is collapsed (`!open`).
  - `ListItemButton` is used for the clickable area.
    - `component={Link}` and `to={item.path}` make it a navigation link.
    - `selected`: Determines if the item is highlighted. It's true if `location.pathname` (from `useLocation()`) matches `item.path`. There's a special case for the "Dashboard" (`/`) to also match if the path starts with `/dashboard`.
    - `sx` prop is used for custom styling, including adjusting padding and icon margin based on the `open` state.
  - `ListItemIcon`: Displays the item's icon. Its color changes if the item is selected.
  - `ListItemText`: Displays the item's text. It's only visible when the sidebar is `open`. Its color also changes if selected.
  - If `item.divider` is true, a `<Divider />` is rendered.

### Example `sidebarItems`

```typescript
const sidebarItems: SidebarItem[] = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Container Mgmt', icon: <StorageIcon />, path: '/container' },
  { text: 'Collect Logs', icon: <FolderOpenIcon />, path: '/collect', divider: true },
  // ... other items ...
  { text: 'Analyze Errors', icon: <InsightsIcon />, path: '/analyze-errors', divider: true },
];
```

This structure allows easy modification and extension of the sidebar navigation.

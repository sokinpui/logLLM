import React from 'react';
import {
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  styled,
  useTheme,
  IconButton,
  Divider,
  Tooltip, // Import Tooltip
} from '@mui/material';
import { Link, useLocation } from 'react-router-dom'; // Import useLocation
import DashboardIcon from '@mui/icons-material/Dashboard';
import StorageIcon from '@mui/icons-material/Storage'; // For Container/DB
import FolderOpenIcon from '@mui/icons-material/FolderOpen'; // For Collect
import TextFieldsIcon from '@mui/icons-material/TextFields'; // For Parsers
import ManageSearchIcon from '@mui/icons-material/ManageSearch'; // For ES-Parse
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck'; // For Prompts Manager
import TimerIcon from '@mui/icons-material/Timer'; // For Normalize-TS
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'; // For Analyze Errors
// import MenuIcon from '@mui/icons-material/Menu'; // Not used directly for toggle here, MainLayout handles it
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

const drawerWidth = 240;

const openedMixin = (theme: any) => ({
  width: drawerWidth,
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: 'hidden',
});

const closedMixin = (theme: any) => ({
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: 'hidden',
  width: `calc(${theme.spacing(7)} + 1px)`,
  [theme.breakpoints.up('sm')]: {
    width: `calc(${theme.spacing(8)} + 1px)`,
  },
});

const StyledDrawer = styled(Drawer, { shouldForwardProp: (prop) => prop !== 'open' })(
  ({ theme, open }: any) => ({
    width: drawerWidth,
    flexShrink: 0,
    whiteSpace: 'nowrap',
    boxSizing: 'border-box',
    ...(open && {
      ...openedMixin(theme),
      '& .MuiDrawer-paper': openedMixin(theme),
    }),
    ...(!open && {
      ...closedMixin(theme),
      '& .MuiDrawer-paper': closedMixin(theme),
    }),
  }),
);

const DrawerHeader = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  padding: theme.spacing(0, 1),
  ...theme.mixins.toolbar,
}));

interface SidebarItem {
  text: string;
  icon: React.ReactElement;
  path: string;
}

const sidebarItems: SidebarItem[] = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Container Mgmt', icon: <StorageIcon />, path: '/container' },
  { text: 'Collect Logs', icon: <FolderOpenIcon />, path: '/collect' },
  { text: 'File Parser', icon: <TextFieldsIcon />, path: '/file-parser' },
  { text: 'ES Parser', icon: <ManageSearchIcon />, path: '/es-parser' },
  { text: 'Normalize TS', icon: <TimerIcon />, path: '/normalize-ts' },
  { text: 'Analyze Errors', icon: <ErrorOutlineIcon />, path: '/analyze-errors' },
  { text: 'Prompts Manager', icon: <PlaylistAddCheckIcon />, path: '/prompts-manager' },
];

interface SidebarProps {
  open: boolean;
  handleDrawerClose: () => void;
  handleDrawerOpen: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ open, handleDrawerClose, handleDrawerOpen }) => {
  const theme = useTheme();
  const location = useLocation(); // For active route styling

  return (
    <StyledDrawer variant="permanent" open={open}>
      <DrawerHeader>
        <IconButton onClick={open ? handleDrawerClose : handleDrawerOpen}>
          {/* Toggle icon based on open state, consistent with drawer behavior */}
          {open ? (theme.direction === 'rtl' ? <ChevronRightIcon /> : <ChevronLeftIcon />) : (theme.direction === 'rtl' ? <ChevronLeftIcon /> : <ChevronRightIcon />) }
        </IconButton>
      </DrawerHeader>
      <Divider />
      <List>
        {sidebarItems.map((item) => (
          <Tooltip title={!open ? item.text : ""} placement="right" key={`${item.text}-tooltip`}>
            <ListItemButton
              key={item.text}
              component={Link}
              to={item.path}
              selected={location.pathname === item.path} // Active route styling
              sx={{
                minHeight: 48,
                justifyContent: open ? 'initial' : 'center',
                px: 2.5,
                '&.Mui-selected': { // Styles for selected item
                  backgroundColor: theme.palette.action.selected,
                  '&:hover': {
                    backgroundColor: theme.palette.action.hover,
                  },
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 0,
                  mr: open ? 3 : 'auto',
                  justifyContent: 'center',
                  color: location.pathname === item.path ? theme.palette.primary.main : 'inherit', // Icon color for active route
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.text}
                sx={{
                  opacity: open ? 1 : 0,
                  color: location.pathname === item.path ? theme.palette.primary.main : 'inherit', // Text color for active route
                }}
              />
            </ListItemButton>
          </Tooltip>
        ))}
      </List>
    </StyledDrawer>
  );
};

export default Sidebar;

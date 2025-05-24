// frontend/src/components/sidebar/Sidebar.tsx
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
  Tooltip,
} from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import DashboardIcon from '@mui/icons-material/Dashboard';
import StorageIcon from '@mui/icons-material/Storage';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import TextFieldsIcon from '@mui/icons-material/TextFields'; // General parsing
import SchemaIcon from '@mui/icons-material/Schema'; // For Static Grok Parser
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import TimerIcon from '@mui/icons-material/Timer';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import GroupWorkIcon from '@mui/icons-material/GroupWork';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

const drawerWidth = 240;

// DEFINE THESE STYLED COMPONENTS AND MIXINS ONCE
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
  divider?: boolean;
}

const sidebarItems: SidebarItem[] = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Container Mgmt', icon: <StorageIcon />, path: '/container' },
  { text: 'Collect Logs', icon: <FolderOpenIcon />, path: '/collect', divider: true },
  { text: 'Group Info', icon: <GroupWorkIcon />, path: '/groups' },
  // { text: 'File Parser (LLM)', icon: <TextFieldsIcon />, path: '/file-parser' },
  { text: 'ES Parser (LLM)', icon: <ManageSearchIcon />, path: '/es-parser' },
  { text: 'Static Grok Parser', icon: <SchemaIcon />, path: '/static-grok-parser', divider: true }, // ADDED
  // { text: 'Normalize TS', icon: <TimerIcon />, path: '/normalize-ts' },
  // { text: 'Analyze Errors', icon: <ErrorOutlineIcon />, path: '/analyze-errors', divider: true },
  // { text: 'Prompts Manager', icon: <PlaylistAddCheckIcon />, path: '/prompts-manager' },
];

interface SidebarProps {
  open: boolean;
  handleDrawerClose: () => void;
  handleDrawerOpen: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ open, handleDrawerClose, handleDrawerOpen }) => {
  const theme = useTheme();
  const location = useLocation();

  return (
    <StyledDrawer variant="permanent" open={open}>
      <DrawerHeader>
        <IconButton onClick={open ? handleDrawerClose : handleDrawerOpen}>
          {open ? (theme.direction === 'rtl' ? <ChevronRightIcon /> : <ChevronLeftIcon />) : (theme.direction === 'rtl' ? <ChevronLeftIcon /> : <ChevronRightIcon />) }
        </IconButton>
      </DrawerHeader>
      <Divider />
      <List>
        {sidebarItems.map((item) => (
          <React.Fragment key={item.text}>
            <Tooltip title={!open ? item.text : ""} placement="right">
              <ListItemButton
                component={Link}
                to={item.path}
                selected={location.pathname === item.path || (item.path === "/" && location.pathname.startsWith("/dashboard"))} // Adjust selection logic if needed
                sx={{
                  minHeight: 48,
                  justifyContent: open ? 'initial' : 'center',
                  px: 2.5,
                  '&.Mui-selected': {
                    backgroundColor: theme.palette.action.selected,
                    '&:hover': { backgroundColor: theme.palette.action.hover },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: 0,
                    mr: open ? 3 : 'auto',
                    justifyContent: 'center',
                    color: location.pathname === item.path ? theme.palette.primary.main : 'inherit',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  sx={{
                    opacity: open ? 1 : 0,
                    color: location.pathname === item.path ? theme.palette.primary.main : 'inherit',
                  }}
                />
              </ListItemButton>
            </Tooltip>
            {item.divider && <Divider sx={{ my: 1 }} />}
          </React.Fragment>
        ))}
      </List>
    </StyledDrawer>
  );
};

// REMOVE THE REDECLARATIONS FROM HERE
// openedMixin = (theme: any) => ({ /* ... */ });
// closedMixin = (theme: any) => ({ /* ... */ });
// StyledDrawer = styled(Drawer, { shouldForwardProp: (prop) => prop !== 'open' })( /* ... */ );
// DrawerHeader = styled('div')(({ theme }) => ({ /* ... */ }));


export default Sidebar;

import React, { createContext, useState, useMemo, ReactNode } from 'react';
import { ThemeProvider as MuiThemeProvider, CssBaseline } from '@mui/material';
import { createLogLLMTheme } from './theme';
import { PaletteMode } from '@mui/material';

interface ThemeContextType {
  toggleTheme: () => void;
  mode: PaletteMode;
}

export const ThemeContext = createContext<ThemeContextType>({
  toggleTheme: () => {},
  mode: 'dark',
});

interface CustomThemeProviderProps {
  children: ReactNode;
}

export const CustomThemeProvider: React.FC<CustomThemeProviderProps> = ({ children }) => {
  const [mode, setMode] = useState<PaletteMode>('dark'); // Default to dark mode

  const themeToggle = useMemo(
    () => ({
      toggleTheme: () => {
        setMode((prevMode) => (prevMode === 'light' ? 'dark' : 'light'));
      },
      mode,
    }),
    [mode]
  );

  const theme = useMemo(() => createLogLLMTheme(mode), [mode]);

  return (
    <ThemeContext.Provider value={themeToggle}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline /> {/* Ensures consistent baseline styling */}
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

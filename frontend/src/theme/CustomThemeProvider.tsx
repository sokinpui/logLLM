// --- Update: frontend/src/theme/CustomThemeProvider.tsx ---
import React, { createContext, useState, useMemo, ReactNode } from 'react';
import { ThemeProvider as MuiThemeProvider, CssBaseline } from '@mui/material';
import { createLogLLMTheme } from './theme';
// import { PaletteMode } from '@mui/material'; // Remove this line

// PaletteMode is often globally available after MUI core imports,
// or you can import it from '@mui/system' or '@mui/material/styles' if specifically needed.
// For use as a type hint, it's often sufficient to just use 'light' | 'dark'.
// However, to be explicit and ensure type safety, let's import it correctly if needed.
// Most directly, it's part of @mui/system, but often just using the string literals is fine.
// For this case, let's try without direct import as MUI often makes it available.
// If type errors persist, import from '@mui/material/styles' or '@mui/system'
import type { PaletteMode } from '@mui/material'; // Correct way if needed from main, but often inferred or from /styles


interface ThemeContextType {
  toggleTheme: () => void;
  mode: PaletteMode;
}

export const ThemeContext = createContext<ThemeContextType>({
  toggleTheme: () => {},
  mode: 'light', // Default PaletteMode
});

interface CustomThemeProviderProps {
  children: ReactNode;
}

export const CustomThemeProvider: React.FC<CustomThemeProviderProps> = ({ children }) => {
  const [mode, setMode] = useState<PaletteMode>('light'); // Default to dark mode

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

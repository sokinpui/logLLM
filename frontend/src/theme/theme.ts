import { createTheme, ThemeOptions } from "@mui/material/styles";
import { PaletteMode } from "@mui/material";

const getDesignTokens = (mode: PaletteMode): ThemeOptions => ({
  palette: {
    mode,
    ...(mode === "dark"
      ? {
          // Dark mode specific palette
          primary: {
            main: "#90caf9", // A light blue, good for dark themes
          },
          secondary: {
            main: "#f48fb1", // A light pink
          },
          background: {
            default: "#121212", // Standard dark background
            paper: "#1e1e1e", // Slightly lighter for paper elements
          },
          text: {
            primary: "#ffffff",
            secondary: "#b0b0b0",
          },
        }
      : {
          // Light mode specific palette (optional, can expand later)
          primary: {
            main: "#1976d2",
          },
          secondary: {
            main: "#dc004e",
          },
          background: {
            default: "#f4f6f8",
            paper: "#ffffff",
          },
        }),
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontSize: "2.5rem", fontWeight: 500 },
    h2: { fontSize: "2rem", fontWeight: 500 },
    h3: { fontSize: "1.75rem", fontWeight: 500 },
    // Add more typography variants as needed
  },
  components: {
    // Example: Customize MuiButton
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none", // No uppercase buttons by default
        },
      },
    },
    // Add other component customizations
  },
});

export const createLogLLMTheme = (mode: PaletteMode) =>
  createTheme(getDesignTokens(mode));

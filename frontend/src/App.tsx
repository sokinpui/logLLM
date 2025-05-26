import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import AppRoutes from './routes/AppRoutes';
import { CustomThemeProvider } from './theme/CustomThemeProvider';

function App() {
  return (
    <CustomThemeProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </CustomThemeProvider>
  );
}

export default App;

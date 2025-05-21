import React from 'react';
import { Typography, Paper } from '@mui/material';

const DashboardPage: React.FC = () => {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body1">
        Welcome to the LogLLM Dashboard. This area will display key metrics and summaries.
        {/* TODO: Implement Dashboard content */}
      </Typography>
    </Paper>
  );
};

export default DashboardPage;

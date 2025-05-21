import React from 'react';
import { Typography, Paper } from '@mui/material';

const CollectPage: React.FC = () => {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Collect Logs
      </Typography>
      <Typography variant="body1">
        This page will allow you to configure and trigger log collection.
        {/* TODO: Implement Log Collection functionality */}
      </Typography>
    </Paper>
  );
};

export default CollectPage;

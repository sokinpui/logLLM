// --- Create file: frontend/src/pages/NotFoundPage.tsx ---
import React from 'react';
import { Typography, Paper, Button } from '@mui/material';
import { Link } from 'react-router-dom';

const NotFoundPage: React.FC = () => (
  <Paper sx={{ p: 3, textAlign: 'center' }}>
    <Typography variant="h3" gutterBottom>404 - Page Not Found</Typography>
    <Typography variant="body1" sx={{ mb: 2 }}>
      Sorry, the page you are looking for does not exist.
    </Typography>
    <Button variant="contained" component={Link} to="/">
      Go to Dashboard
    </Button>
  </Paper>
);
export default NotFoundPage;

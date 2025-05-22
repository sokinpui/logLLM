// --- Finalized: frontend/src/pages/ContainerPage.tsx ---
import React, { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  CircularProgress,
  Alert,
  FormGroup,
  FormControlLabel,
  Switch,
  Divider,
  Chip,
  Box,
  List,
  ListItem,
  ListItemText,
  IconButton,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import RefreshIcon from '@mui/icons-material/Refresh';

import * as containerService from '../services/containerService';
import type { ContainerStatusItem, ApiError } from '../types/api';

const ContainerPage: React.FC = () => {
  const [statuses, setStatuses] = useState<ContainerStatusItem[]>([]);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<{
    start?: boolean;
    stop?: boolean;
    restart?: boolean;
  }>({});
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [removeOnStop, setRemoveOnStop] = useState<boolean>(false);

  const fetchStatus = useCallback(async (showLoadingSpinner: boolean = true) => {
    if (showLoadingSpinner) setLoadingStatus(true);
    setError(null);
    // Keep previous success message or clear it? For now, let's clear it on manual refresh.
    // If an action was just performed, its success message will be set by handleAction.
    // setSuccessMessage(null);
    try {
      const data = await containerService.getContainerStatus();
      if (data && Array.isArray(data.statuses)) {
        setStatuses(data.statuses);
      } else {
        console.error("Invalid status data received from API:", data);
        setError("Received invalid status data from the server.");
        setStatuses([]);
      }
    } catch (err) {
      const apiError = err as ApiError;
      let errorMessage = 'Failed to fetch container status.';
      if (typeof apiError.detail === 'string') {
        errorMessage = apiError.detail;
      } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0 && typeof apiError.detail[0] === 'object' && apiError.detail[0].msg) {
        errorMessage = apiError.detail[0].msg;
      }
      setError(errorMessage);
      setStatuses([]);
    } finally {
      if (showLoadingSpinner) setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleAction = async (
    action: () => Promise<any>,
    actionName: keyof typeof actionLoading,
    successMsgPrefix: string,
  ) => {
    setActionLoading((prev) => ({ ...prev, [actionName]: true }));
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await action();
      setSuccessMessage(`${successMsgPrefix}: ${response.message}`);
      // Wait a brief moment before refreshing status to allow backend to process
      setTimeout(() => fetchStatus(false), 1500);
    } catch (err) {
      const apiError = err as ApiError;
      let errorMessage = `Failed to ${actionName} containers.`;
      if (typeof apiError.detail === 'string') {
        errorMessage = apiError.detail;
      } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0 && typeof apiError.detail[0] === 'object' && apiError.detail[0].msg) {
        errorMessage = apiError.detail[0].msg;
      }
      setError(errorMessage);
    } finally {
      setActionLoading((prev) => ({ ...prev, [actionName]: false }));
    }
  };

  const handleStart = () => {
    handleAction(containerService.startContainers, 'start', 'Start command sent');
  };

  const handleStop = () => {
    handleAction(
      () => containerService.stopContainers({ remove: removeOnStop }),
      'stop',
      'Stop command sent',
    );
  };

  const handleRestart = () => {
    handleAction(
      containerService.restartContainers,
      'restart',
      'Restart command sent',
    );
  };

  const getStatusChipColor = (status?: string): "success" | "error" | "default" | "warning" => {
    if (typeof status !== 'string') return 'default';
    const lowerStatus = status.toLowerCase();
    if (lowerStatus.includes('running')) return 'success';
    if (lowerStatus.includes('up') && lowerStatus.includes('second')) return 'success'; // For "Up X seconds"
    if (lowerStatus.includes('stopped') || lowerStatus.includes('exited')) return 'error';
    if (lowerStatus.includes('not found')) return 'default';
    return 'warning'; // for creating, restarting, unhealthy etc.
  };

  const formatContainerName = (name?: string): string => {
    if (typeof name !== 'string' || !name) return "Unknown Container";
    // A more generic approach to pretty print common container names
    return name
      .replace(/^movelook_/, '') // Remove common prefix
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const isAnyActionLoading = Object.values(actionLoading).some(Boolean);

  return (
    <Paper sx={{ p: 3, maxWidth: 800, margin: 'auto' }}>
      <Typography variant="h4" gutterBottom sx={{ textAlign: 'center', mb: 3 }}>
        Services Management
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1}}>
            <Typography variant="h6">
              Current Status
            </Typography>
            <IconButton
              onClick={() => fetchStatus(true)}
              size="small"
              disabled={loadingStatus || isAnyActionLoading}
              title="Refresh Status"
            >
              <RefreshIcon />
            </IconButton>
          </Box>
          {loadingStatus ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
              <CircularProgress />
            </Box>
          ) : statuses && statuses.length > 0 ? (
            <List dense>
              {statuses.map((s, index) => {
                if (!s || typeof s.name !== 'string' || typeof s.status !== 'string') {
                  return (
                    <ListItem key={`error-item-${index}`}>
                      <ListItemText primary="Error: Invalid status item data from API." />
                    </ListItem>
                  );
                }
                return (
                  <ListItem key={s.name} sx={{ py: 0.5 }}>
                    <ListItemText
                      primary={formatContainerName(s.name)}
                    />
                    <Chip
                      label={s.status || "N/A"}
                      color={getStatusChipColor(s.status)}
                      size="small"
                    />
                  </ListItem>
                );
              })}
            </List>
          ) : (
            <Typography color="text.secondary" sx={{textAlign: 'center', my: 2}}>
                No status information available. The backend might be down or services not yet started.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} sm={4}>
          <Button
            variant="contained"
            color="success"
            onClick={handleStart}
            startIcon={actionLoading.start ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
            disabled={loadingStatus || isAnyActionLoading}
            fullWidth
          >
            Start Services
          </Button>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Button
            variant="contained"
            color="error"
            onClick={handleStop}
            startIcon={actionLoading.stop ? <CircularProgress size={20} color="inherit" /> : <StopIcon />}
            disabled={loadingStatus || isAnyActionLoading}
            fullWidth
          >
            Stop Services
          </Button>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Button
            variant="outlined"
            color="primary"
            onClick={handleRestart}
            startIcon={actionLoading.restart ? <CircularProgress size={20} color="inherit" /> : <RestartAltIcon />}
            disabled={loadingStatus || isAnyActionLoading}
            fullWidth
          >
            Restart Services
          </Button>
        </Grid>
        <Grid item xs={12} sx={{ mt: 1, display: 'flex', justifyContent: 'center' }}>
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={removeOnStop}
                  onChange={(e) => setRemoveOnStop(e.target.checked)}
                  disabled={loadingStatus || isAnyActionLoading}
                />
              }
              label="Remove containers on stop"
            />
          </FormGroup>
        </Grid>
      </Grid>
      <Divider sx={{my:3}}/>
      <Typography variant="body2" color="textSecondary" sx={{textAlign: 'center'}}>
        These actions manage the Elasticsearch and Kibana Docker containers.
        Ensure Docker is running. Status updates may take a few moments to reflect.
      </Typography>
    </Paper>
  );
};

export default ContainerPage;

// frontend/src/pages/ContainerPage.tsx
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
  Tooltip,
  Stack,
  TableContainer,
  Table,
  TableBody,
  TableRow,
  TableCell,
  Link as MuiLink,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import RefreshIcon from '@mui/icons-material/Refresh';
import StorageIcon from '@mui/icons-material/Storage';
import DnsIcon from '@mui/icons-material/Dns';
import IdIcon from '@mui/icons-material/Fingerprint';
import PortIcon from '@mui/icons-material/SettingsEthernet';
import MountIcon from '@mui/icons-material/BackupTable';
import ServiceIcon from '@mui/icons-material/MiscellaneousServices';
import LinkIcon from '@mui/icons-material/Link';

import * as containerService from '../services/containerService';
import type { ContainerDetailItem, VolumeDetailItem, ApiError } from '../types/api';

// Local Storage Key
const LS_CONTAINER_REMOVE_ON_STOP = 'logllm_container_removeOnStop';

const ContainerPage: React.FC = () => {
  const [containerDetails, setContainerDetails] = useState<ContainerDetailItem[]>([]);
  const [volumeInfo, setVolumeInfo] = useState<VolumeDetailItem | null>(null);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<{
    start?: boolean;
    stop?: boolean;
    restart?: boolean;
  }>({});
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [removeOnStop, setRemoveOnStop] = useState<boolean>(() => {
    const storedValue = localStorage.getItem(LS_CONTAINER_REMOVE_ON_STOP);
    if (storedValue) {
      try {
        return JSON.parse(storedValue);
      } catch (e) {
        console.error("Failed to parse removeOnStop from localStorage", e);
        return false;
      }
    }
    return false;
  });

  // Save removeOnStop to Local Storage
  useEffect(() => {
    localStorage.setItem(LS_CONTAINER_REMOVE_ON_STOP, JSON.stringify(removeOnStop));
  }, [removeOnStop]);

  const fetchStatus = useCallback(async (showLoadingSpinner: boolean = true) => {
    if (showLoadingSpinner) setLoadingStatus(true);
    setError(null);
    try {
      const data = await containerService.getContainerStatus();
      if (data && Array.isArray(data.statuses)) {
        setContainerDetails(data.statuses);
      } else {
        console.error("Invalid container status data received from API:", data.statuses);
        setError("Received invalid container status data from the server.");
        setContainerDetails([]);
      }
      if (data && data.volume_info) {
        setVolumeInfo(data.volume_info);
      } else {
        setVolumeInfo(null);
      }
    } catch (err) {
      const apiError = err as ApiError;
      let errorMessage = 'Failed to fetch service status.';
      if (typeof apiError.detail === 'string') {
        errorMessage = apiError.detail;
      } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0 && typeof apiError.detail[0] === 'object' && apiError.detail[0].msg) {
        errorMessage = apiError.detail[0].msg;
      }
      setError(errorMessage);
      setContainerDetails([]);
      setVolumeInfo(null);
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
      setTimeout(() => fetchStatus(false), 3500);
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

  const getContainerStatusChipColor = (status?: string): "success" | "error" | "default" | "warning" => {
    if (typeof status !== 'string') return 'default';
    const lowerStatus = status.toLowerCase();
    if (lowerStatus.includes('running')) return 'success';
    if (lowerStatus.includes('up') && (lowerStatus.includes('second') || lowerStatus.includes('minute') || lowerStatus.includes('hour'))) return 'success';
    if (lowerStatus.includes('stopped') || lowerStatus.includes('exited')) return 'error';
    if (lowerStatus.includes('not found') || lowerStatus.includes('not_found')) return 'default';
    if (lowerStatus.includes('error')) return 'error';
    return 'warning';
  };

  const getServiceStatusChipColor = (serviceStatus?: string | null): "success" | "warning" | "error" | "default" => {
    if (!serviceStatus || serviceStatus === "N/A") return 'default';
    const lowerStatus = serviceStatus.toLowerCase();

    if (lowerStatus === 'green' || lowerStatus === 'available') return 'success';
    if (lowerStatus === 'yellow' || lowerStatus === 'degraded') return 'warning';
    if (lowerStatus.includes('error') || lowerStatus === 'red' || lowerStatus === 'critical' || lowerStatus === 'unreachable' || lowerStatus === 'timeout' || lowerStatus === 'unavailable') return 'error';
    if (lowerStatus === 'container not running' || lowerStatus === 'port n/a' || lowerStatus === 'unknown') return 'default';
    return 'default';
};


  const formatContainerName = (name?: string): string => {
    if (typeof name !== 'string' || !name) return "Unknown Container";
    return name
      .replace(/^movelook_/, '')
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const isAnyActionLoading = Object.values(actionLoading).some(Boolean);

  const renderDetailRow = (icon: React.ReactNode, label: string, value?: string | string[] | null) => {
    if (!value || (Array.isArray(value) && value.length === 0)) {
      return null;
    }
    return (
      <TableRow>
        <TableCell sx={{ borderBottom: 'none', py: 0.5, width: 'auto', pr:1 }}>
            <Stack direction="row" alignItems="center" spacing={1}>{icon} <Typography variant="caption" fontWeight="medium">{label}:</Typography></Stack>
        </TableCell>
        <TableCell sx={{ borderBottom: 'none', py: 0.5 }}>
          {Array.isArray(value) ? (
            <List dense sx={{p:0, m:0}}>
              {value.map((item, idx) => <ListItem key={idx} sx={{p:0, m:0}}><Typography variant="caption" color="text.secondary">{item}</Typography></ListItem>)}
            </List>
          ) : (
            <Typography variant="caption" color="text.secondary">{value}</Typography>
          )}
        </TableCell>
      </TableRow>
    );
  }


  return (
    <Paper sx={{ p: 3, maxWidth: 900, margin: 'auto' }}>
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
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2}}>
        <Tooltip title="Refresh Status">
            <IconButton
            onClick={() => fetchStatus(true)}
            disabled={loadingStatus || isAnyActionLoading}
            >
            <RefreshIcon />
            </IconButton>
        </Tooltip>
      </Box>

      {loadingStatus ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 5 }}>
          <CircularProgress size={50} />
        </Box>
      ) : (
        <Grid container spacing={3}>
          {containerDetails && containerDetails.map((detail) => (
            <Grid item xs={12} md={6} key={detail.name}>
              <Card elevation={3}>
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={1.5}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <DnsIcon color={getContainerStatusChipColor(detail.status) === 'success' ? 'success' : getContainerStatusChipColor(detail.status) === 'error' ? 'error' : 'action'}/>
                        <Typography variant="h6">{formatContainerName(detail.name)}</Typography>
                    </Stack>
                    <Chip
                      label={detail.status || "N/A"}
                      color={getContainerStatusChipColor(detail.status)}
                      size="small"
                    />
                  </Stack>
                  <Divider sx={{my:1}}/>
                  <TableContainer>
                    <Table size="small">
                      <TableBody>
                        {renderDetailRow(<IdIcon fontSize="small"/>, "ID", detail.short_id || detail.container_id?.substring(0,12))}
                        {renderDetailRow(<PortIcon fontSize="small"/>, "Ports", detail.ports)}
                        {renderDetailRow(<MountIcon fontSize="small"/>, "Mounts", detail.mounts)}
                        <TableRow>
                            <TableCell sx={{ borderBottom: 'none', py: 0.5, pr:1 }}>
                                <Stack direction="row" alignItems="center" spacing={1}>
                                    <ServiceIcon fontSize="small" />
                                    <Typography variant="caption" fontWeight="medium">Service:</Typography>
                                </Stack>
                            </TableCell>
                            <TableCell sx={{ borderBottom: 'none', py: 0.5 }}>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    {detail.service_status && detail.service_status !== "N/A" && (
                                        <Chip
                                            label={detail.service_status}
                                            color={getServiceStatusChipColor(detail.service_status)}
                                            size="small"
                                        />
                                    )}
                                    {detail.name.toLowerCase().includes('kibana') && detail.service_url && detail.service_status?.toLowerCase() === 'available' && (
                                        <Button
                                            component={MuiLink}
                                            href={detail.service_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            size="small"
                                            variant="outlined"
                                            startIcon={<LinkIcon />}
                                            sx={{textTransform: 'none', fontSize: '0.75rem', py:0.2, px:0.8, lineHeight: 1.5 }}
                                        >
                                            Open Kibana
                                        </Button>
                                    )}
                                     {(detail.service_status === "N/A" || !detail.service_status) && (
                                        <Typography variant="caption" color="text.secondary">N/A</Typography>
                                     )}
                                </Stack>
                            </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          ))}

          {volumeInfo && (
             <Grid item xs={12} md={containerDetails.length % 2 !== 0 ? 6 : 12}>
                <Card elevation={3}>
                    <CardContent>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={1.5}>
                         <Stack direction="row" alignItems="center" spacing={1}>
                            <StorageIcon color={getContainerStatusChipColor(volumeInfo.status) === 'success' || volumeInfo.status === 'found' ? 'success' : getContainerStatusChipColor(volumeInfo.status) === 'error' ? 'error' : 'action'}/>
                            <Typography variant="h6">Volume: {volumeInfo.name}</Typography>
                        </Stack>
                        <Chip
                            label={volumeInfo.status || "N/A"}
                            color={getContainerStatusChipColor(volumeInfo.status === 'found' ? 'running' : volumeInfo.status)}
                            size="small"
                        />
                    </Stack>
                    <Divider sx={{my:1}}/>
                    <TableContainer>
                        <Table size="small">
                        <TableBody>
                            {renderDetailRow(<IdIcon fontSize="small"/>,"Driver", volumeInfo.driver)}
                            {renderDetailRow(<MountIcon fontSize="small"/>,"Mountpoint", volumeInfo.mountpoint)}
                            {renderDetailRow(<DnsIcon fontSize="small"/>,"Scope", volumeInfo.scope)}
                        </TableBody>
                        </Table>
                    </TableContainer>
                    </CardContent>
                </Card>
            </Grid>
          )}
           {!volumeInfo && !loadingStatus && (
             <Grid item xs={12}>
                <Typography color="text.secondary" sx={{textAlign: 'center', my: 2}}>
                    Volume information not available.
                </Typography>
             </Grid>
           )}
        </Grid>
      )}

      {(!containerDetails || containerDetails.length === 0) && !loadingStatus && (
         <Typography color="text.secondary" sx={{textAlign: 'center', my: 3}}>
            No container status information available. Backend might be down or services not started.
        </Typography>
      )}


      <Divider sx={{my:3}}/>
      <Grid container spacing={2} alignItems="center" justifyContent="center">
        <Grid item xs={12} sm={6} md={3}>
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
        <Grid item xs={12} sm={6} md={3}>
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
        <Grid item xs={12} sm={6} md={3}>
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
         <Grid item xs={12} sm={6} md={3} sx={{ display: 'flex', justifyContent: 'center' }}>
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={removeOnStop}
                  onChange={(e) => setRemoveOnStop(e.target.checked)}
                  disabled={loadingStatus || isAnyActionLoading}
                  size="small"
                />
              }
              label={<Typography variant="body2">Remove on stop</Typography>}
            />
          </FormGroup>
        </Grid>
      </Grid>
      <Typography variant="caption" color="textSecondary" component="p" sx={{textAlign: 'center', mt: 3}}>
        These actions manage the Elasticsearch and Kibana Docker containers.
        Ensure Docker is running. Status updates may take a few moments to reflect.
      </Typography>
    </Paper>
  );
};

export default ContainerPage;

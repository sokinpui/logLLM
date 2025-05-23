import React, { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Paper,
  TextField,
  Button,
  Box,
  CircularProgress,
  Alert,
  Collapse,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Grid,
  LinearProgress,
  Chip,
  Card // Added Card for better layout of analysis results
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import FolderZipIcon from '@mui/icons-material/FolderZip';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ScienceIcon from '@mui/icons-material/Science';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';

import * as collectService from '../services/collectService';
import type { ApiError } from '../types/api';
import type { DirectoryAnalysisResponse, GroupInfo, TaskStatusResponse } from '../types/collect';

// localStorage keys
const LS_COLLECT_PATH_KEY = 'logllm_collect_serverDirectoryPath';
const LS_COLLECT_ANALYSIS_KEY_PREFIX = 'logllm_collect_analysisResult_'; // Appended with path
const LS_COLLECT_TASK_ID_KEY = 'logllm_collect_collectionTaskId';

const CollectPage: React.FC = () => {
  const [serverDirectoryPath, setServerDirectoryPath] = useState<string>('');
  const [analysisResult, setAnalysisResult] = useState<DirectoryAnalysisResponse | null>(null);
  const [isAnalyzingPath, setIsAnalyzingPath] = useState<boolean>(false);

  const [collectionTaskId, setCollectionTaskId] = useState<string | null>(null);
  const [collectionStatus, setCollectionStatus] = useState<TaskStatusResponse | null>(null);
  const [isStartingCollection, setIsStartingCollection] = useState<boolean>(false);
  const [isPollingStatus, setIsPollingStatus] = useState<boolean>(false);

  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load initial state from localStorage
  useEffect(() => {
    const savedPath = localStorage.getItem(LS_COLLECT_PATH_KEY);
    if (savedPath) {
      setServerDirectoryPath(savedPath);
      // Try to load analysis for this path
      const savedAnalysis = localStorage.getItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + savedPath);
      if (savedAnalysis) {
        try {
          const parsedAnalysis = JSON.parse(savedAnalysis);
          // Basic validation of stored analysis
          if (parsedAnalysis && parsedAnalysis.scanned_path === savedPath) {
             setAnalysisResult(parsedAnalysis);
          } else {
            localStorage.removeItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + savedPath); // Clean up invalid stored data
          }
        } catch (e) {
          console.error("Failed to parse saved analysis result:", e);
          localStorage.removeItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + savedPath);
        }
      }
    }

    const savedTaskId = localStorage.getItem(LS_COLLECT_TASK_ID_KEY);
    if (savedTaskId) {
      setCollectionTaskId(savedTaskId);
      // Polling will be triggered by useEffect watching collectionTaskId
    }
  }, []);

  // Save serverDirectoryPath to localStorage
  useEffect(() => {
    if (serverDirectoryPath) {
      localStorage.setItem(LS_COLLECT_PATH_KEY, serverDirectoryPath);
    } else {
      // If path is cleared, remove it and its associated analysis
      localStorage.removeItem(LS_COLLECT_PATH_KEY);
      const oldPath = localStorage.getItem(LS_COLLECT_PATH_KEY); // Get previous path to remove its analysis
      if (oldPath) localStorage.removeItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + oldPath);
    }
  }, [serverDirectoryPath]);

  // Save analysisResult to localStorage, keyed by path
  useEffect(() => {
    if (analysisResult && analysisResult.scanned_path) {
      localStorage.setItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + analysisResult.scanned_path, JSON.stringify(analysisResult));
    }
    // No explicit removal here, old analysis for different paths remain until path is reused or cleared
  }, [analysisResult]);

  // Save collectionTaskId to localStorage
  useEffect(() => {
    if (collectionTaskId) {
      localStorage.setItem(LS_COLLECT_TASK_ID_KEY, collectionTaskId);
    } else {
      localStorage.removeItem(LS_COLLECT_TASK_ID_KEY);
    }
  }, [collectionTaskId]);


  const handleAnalyzePath = async () => {
    if (!serverDirectoryPath.trim()) {
      setError('Server directory path cannot be empty.');
      return;
    }
    setIsAnalyzingPath(true);
    setError(null);
    setSuccessMessage(null);
    setAnalysisResult(null); // Clear previous analysis
    setCollectionTaskId(null); // Clear previous task
    setCollectionStatus(null);
    setIsStartingCollection(false);
    setIsPollingStatus(false);

    try {
      const response = await collectService.analyzeServerPathStructure({ directory: serverDirectoryPath });
      setAnalysisResult(response); // This will trigger the useEffect to save it
      if (response.error_message) {
        setError(`Analysis Error: ${response.error_message}`);
      } else if (!response.path_exists) {
        setError(`Path not found on server: ${response.scanned_path}`);
      }
    } catch (err) {
      const apiError = err as ApiError;
      let errorMessage = 'Failed to analyze server path.';
      if (typeof apiError.detail === 'string') {
        errorMessage = apiError.detail;
      } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0 && typeof apiError.detail[0] === 'object' && apiError.detail[0].msg) {
        errorMessage = apiError.detail[0].msg;
      } else if ((err as Error).message) {
        errorMessage = (err as Error).message;
      }
      setError(errorMessage);
    } finally {
      setIsAnalyzingPath(false);
    }
  };

  const handleStartCollection = async () => {
    if (!analysisResult || analysisResult.error_message || !analysisResult.path_exists ) {
      setError('Cannot start collection. Please analyze a valid directory path first.');
      return;
    }
    if (analysisResult.root_files_present) {
      setError('Collection blocked: Root files detected. Logs must be in subdirectories (groups).');
      return;
    }
    if (analysisResult.identified_groups.length === 0) {
      setError('Collection blocked: No groups (subdirectories with logs) found in the specified path.');
      return;
    }

    setIsStartingCollection(true);
    setError(null);
    setSuccessMessage(null);
    setCollectionTaskId(null); // Clear previous task before starting new one
    setCollectionStatus(null);

    try {
      const response = await collectService.startCollectionFromServerPath({ directory: analysisResult.scanned_path });
      setSuccessMessage(response.message);
      if (response.task_id) {
        setCollectionTaskId(response.task_id); // This will trigger useEffect for saving and polling
      } else {
        setError("Collection initiated but no Task ID received.");
        setIsStartingCollection(false);
      }
    } catch (err) {
      const apiError = err as ApiError;
      let errorMessage = 'Failed to start collection task.';
      if (typeof apiError.detail === 'string') {
        errorMessage = apiError.detail;
      } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0 && typeof apiError.detail[0] === 'object' && apiError.detail[0].msg) {
        errorMessage = apiError.detail[0].msg;
      } else if ((err as Error).message) {
        errorMessage = (err as Error).message;
      }
      setError(errorMessage);
      setIsStartingCollection(false);
    }
  };

  // Polling logic for task status
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    if (collectionTaskId && !collectionStatus?.completed) {
        setIsPollingStatus(true);
        setIsStartingCollection(false);

      const poll = async () => {
        try {
          const statusRes = await collectService.getCollectionTaskStatus(collectionTaskId);
          setCollectionStatus(statusRes);
          if (statusRes.completed) {
            if (intervalId) clearInterval(intervalId);
            setIsPollingStatus(false);
            if(statusRes.error) {
                setError(`Collection Task Error: ${statusRes.error}`);
                setSuccessMessage(null);
            } else {
                setSuccessMessage(prev => `${prev || 'Collection task started.'} Task ${statusRes.task_id.substring(0,8)} Completed: ${statusRes.status} - ${statusRes.progress_detail || ''}`);
            }
            // Potentially clear task ID from localStorage after some time or on user action
            // For now, it remains, so refresh will try to poll a completed task.
          }
        } catch (err) {
          console.error("Failed to fetch task status:", err);
          // If task ID is not found (404), it means it's old or invalid, clear it
          if ((err as any)?.response?.status === 404 || (err as Error).message?.toLowerCase().includes('not found')) {
            setError(`Task ID ${collectionTaskId.substring(0,8)} not found. It might be an old task. Clearing.`);
            setCollectionTaskId(null);
            setCollectionStatus(null);
            if (intervalId) clearInterval(intervalId);
            setIsPollingStatus(false);
          }
        }
      };

      poll();
      intervalId = setInterval(poll, 3000);
    } else if (collectionStatus?.completed) {
        setIsPollingStatus(false);
        setIsStartingCollection(false);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [collectionTaskId, collectionStatus?.completed]); // Added collectionStatus?.completed to dependencies


  const isLoading = isAnalyzingPath || isStartingCollection || isPollingStatus;

  const handlePathInputChange = (newPath: string) => {
    setServerDirectoryPath(newPath);
    // If user changes path, clear analysis and task details for the *old* path
    if (newPath !== serverDirectoryPath) {
        setAnalysisResult(null);
        setCollectionTaskId(null);
        setCollectionStatus(null);
        setError(null);
        // Attempt to load analysis if there's a saved one for the new path
        const savedAnalysisForNewPath = localStorage.getItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + newPath);
        if (savedAnalysisForNewPath) {
            try {
                const parsedAnalysis = JSON.parse(savedAnalysisForNewPath);
                 if (parsedAnalysis && parsedAnalysis.scanned_path === newPath) {
                    setAnalysisResult(parsedAnalysis);
                 } else {
                    localStorage.removeItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + newPath);
                 }
            } catch (e) {
                localStorage.removeItem(LS_COLLECT_ANALYSIS_KEY_PREFIX + newPath);
            }
        }
    }
  };


  return (
    <Paper sx={{ p: 3, maxWidth: 800, margin: 'auto' }}>
      <Typography variant="h4" gutterBottom sx={{ textAlign: 'center', mb: 1 }}>
        Collect Logs from Server
      </Typography>
      <Typography variant="body2" color="textSecondary" sx={{ textAlign: 'center', mb: 3 }}>
        Enter an absolute path on the server. The system will analyze its structure,
        then you can initiate collection. Path and task state are remembered across refreshes.
      </Typography>

      <Collapse in={!!error}>
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      </Collapse>
      <Collapse in={!!successMessage && (!isLoading || (collectionStatus?.completed && !collectionStatus?.error))}>
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      </Collapse>

      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 2 }}>
        <TextField
          label="Server Directory Path (Absolute)"
          variant="outlined"
          fullWidth
          value={serverDirectoryPath}
          onChange={(e) => handlePathInputChange(e.target.value)}
          disabled={isLoading}
          sx={{flexGrow: 1}}
          helperText="e.g., /var/log/my_app_logs or C:\logs\my_app"
        />
        <Button
          variant="outlined"
          onClick={handleAnalyzePath}
          disabled={isLoading || !serverDirectoryPath.trim()}
          startIcon={isAnalyzingPath ? <CircularProgress size={20} /> : <ScienceIcon />}
          sx={{height: '56px'}}
        >
          Analyze Path
        </Button>
      </Box>

      {analysisResult && !isAnalyzingPath && (
        <Card variant="outlined" sx={{ mb: 2, p: 2 }}>
            <Typography variant="h6" gutterBottom>
                Analysis for: <Chip label={analysisResult.scanned_path} size="small" onDelete={analysisResult.error_message || !analysisResult.path_exists ? ()=>setAnalysisResult(null) : undefined }/>
            </Typography>
          {!analysisResult.path_exists ? (
            <Alert severity="error">Path does not exist on server.</Alert>
          ) : analysisResult.error_message ? (
            <Alert severity="error">Analysis Error: {analysisResult.error_message}</Alert>
          ) : (
            <>
              {analysisResult.root_files_present && (
                <Alert severity="warning" icon={<ErrorOutlineIcon fontSize="inherit" />} sx={{mb:1}}>Root files detected! Collection blocked. Logs must be in subdirectories (groups).</Alert>
              )}
              <Typography variant="subtitle2" sx={{mt:1}}>Identified Groups:</Typography>
              {analysisResult.identified_groups.length > 0 ? (
                <List dense>
                  {analysisResult.identified_groups.map((group: GroupInfo) => (
                    <ListItem key={group.name} disablePadding>
                      <ListItemIcon sx={{minWidth: 30}}><FolderZipIcon fontSize="small" color="primary"/></ListItemIcon>
                      <ListItemText primary={`${group.name} (${group.file_count} file(s))`} />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="caption" color="textSecondary">No subdirectories with log files found.</Typography>
              )}

              {(!analysisResult.root_files_present && analysisResult.identified_groups.length > 0) &&
                <Alert severity="success" icon={<CheckCircleOutlineIcon fontSize="inherit" />} sx={{mt:1}}>Structure is valid for collection.</Alert>
              }
               {(!analysisResult.root_files_present && analysisResult.identified_groups.length === 0) &&
                <Alert severity="warning" icon={<ErrorOutlineIcon fontSize="inherit" />} sx={{mt:1}}>No groups found. Cannot start collection.</Alert>
              }
            </>
          )}
        </Card>
      )}

      {analysisResult && !analysisResult.error_message && analysisResult.path_exists && !isAnalyzingPath && (
          <Button
            variant="contained"
            color="primary"
            fullWidth
            onClick={handleStartCollection}
            disabled={isLoading || analysisResult.root_files_present || analysisResult.identified_groups.length === 0}
            startIcon={isStartingCollection || isPollingStatus ? <CircularProgress size={20} color="inherit"/> : <PlayCircleOutlineIcon />}
            size="large"
            sx={{mt:1, mb:2}}
          >
            {isStartingCollection ? 'Initiating...' : isPollingStatus && !collectionStatus?.completed ? `Collecting... (${collectionStatus?.status || 'Fetching Status'})` : 'Start Collection'}
          </Button>
      )}

      {collectionTaskId && (
        <Box sx={{ mt: 2, p:2, border: '1px solid', borderColor: 'divider', borderRadius: 1}}>
          <Typography variant="subtitle1" gutterBottom>
            Collection Progress (Task ID: <Chip label={collectionTaskId.substring(0,8)} size="small" color="secondary"/>)
          </Typography>
          {collectionStatus ? (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Box sx={{ width: '100%', mr: 1 }}>
                   <LinearProgress
                    variant={collectionStatus.completed || collectionStatus.status === "Initializing" || collectionStatus.status === "Pending" ? "determinate" : "indeterminate" }
                    value={collectionStatus.completed ? 100 : (collectionStatus.status === "Processing" ? 50 : (collectionStatus.status === "Scanning directory" ? 25 : 10))}
                  />
                </Box>
                <Box sx={{ minWidth: 35 }}>
                  <Typography variant="body2" color="text.secondary">
                    {`${collectionStatus.completed ? 100 : (collectionStatus.status === "Processing" ? 50 : (collectionStatus.status === "Scanning directory" ? 25 : 10))}%`}
                  </Typography>
                </Box>
              </Box>
              <Typography variant="body2">Status: <strong>{collectionStatus.status}</strong></Typography>
              {collectionStatus.progress_detail && <Typography variant="caption" color="textSecondary">Details: {collectionStatus.progress_detail}</Typography>}
              {collectionStatus.error && <Alert severity="error" sx={{mt:1}}>Error: {collectionStatus.error}</Alert>}
              {collectionStatus.completed && !collectionStatus.error &&
                <Alert severity="success" sx={{mt:1}}>Task completed successfully!</Alert>
              }
            </>
          ) : (
            <Box sx={{display:'flex', alignItems:'center', gap:1}}> <CircularProgress size={16}/> <Typography variant="body2">Fetching initial status for task {collectionTaskId.substring(0,8)}...</Typography> </Box>
          )}
        </Box>
      )}


      <Divider sx={{ my: 3 }} />
      <Typography variant="body2" color="textSecondary" sx={{ mt: 2, textAlign: 'center' }}>
        <strong>Instructions:</strong>
        <ol style={{ textAlign: 'left', display: 'inline-block', marginTop: '8px', paddingLeft: '20px' }}>
          <li>Enter the absolute path to the log directory on the server.</li>
          <li>Click "Analyze Path" to check its structure. Logs must be in subdirectories (groups).</li>
          <li>If the structure is valid, click "Start Collection".</li>
          <li>The server will then process logs from that path. Progress will be displayed above.</li>
        </ol>
      </Typography>
    </Paper>
  );
};

export default CollectPage;

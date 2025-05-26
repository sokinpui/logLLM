// frontend/src/pages/AnalyzeErrorsPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Typography, Grid, TextField, Button, Paper, Box, CircularProgress,
  Alert, Divider, Chip, Accordion, AccordionSummary, AccordionDetails,
  Tooltip, IconButton, Select, MenuItem, InputLabel, FormControl, Card, CardContent,
  LinearProgress, Stack, List, ListItem, ListItemText,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Link as MuiLink, Collapse,
  TablePagination,
  Switch,
  FormControlLabel
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ScienceIcon from '@mui/icons-material/Science';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import InfoIcon from '@mui/icons-material/Info';


import { DateTimePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';


import * as analyzeErrorsService from '../services/analyzeErrorsService';
import * as groupService from '../services/groupService';
import type { ApiError } from '../types/api';
import type { GroupInfoDetail } from '../types/group';
import type {
  AnalyzeErrorsRunParams,
  AnalyzeErrorsTaskStatusResponse,
  AnalysisResultSummary,
  ProcessedClusterDetail,
  LogClusterSummaryOutput,
  ErrorSummaryListItem,
  ListErrorSummariesResponse
} from '../types/analyzeErrors';


// Config defaults
const DEFAULT_ERROR_LEVELS_STRING = "error,critical,fatal,warn";
const DEFAULT_MAX_LOGS_FOR_SUMMARY = 5000;
const DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2";
const DEFAULT_LLM_FOR_SUMMARY = "gemini-1.5-flash-latest";
const DEFAULT_DBSCAN_EPS = 0.3;
const DEFAULT_DBSCAN_MIN_SAMPLES = 2;
const DEFAULT_MAX_SAMPLES_CLUSTER = 5;
const DEFAULT_MAX_SAMPLES_UNCLUSTERED = 10;
const DEFAULT_TARGET_SUMMARY_INDEX = "log_error_summaries";


// Local Storage Keys
const LS_AE_PREFIX = 'logllm_analyzeerrors_';
const LS_AE_GROUP_NAME = `${LS_AE_PREFIX}groupName`;
const LS_AE_START_TIME = `${LS_AE_PREFIX}startTime`;
const LS_AE_END_TIME = `${LS_AE_PREFIX}endTime`;
const LS_AE_ERROR_LEVELS = `${LS_AE_PREFIX}errorLevels`;
const LS_AE_MAX_LOGS = `${LS_AE_PREFIX}maxLogs`;
const LS_AE_EMBED_MODEL = `${LS_AE_PREFIX}embedModel`;
const LS_AE_LLM_MODEL = `${LS_AE_PREFIX}llmModel`;
const LS_AE_DBSCAN_EPS = `${LS_AE_PREFIX}dbscanEps`;
const LS_AE_DBSCAN_MINS = `${LS_AE_PREFIX}dbscanMinSamples`;
const LS_AE_MAX_SAMPLES_C = `${LS_AE_PREFIX}maxSamplesCluster`;
const LS_AE_MAX_SAMPLES_UC = `${LS_AE_PREFIX}maxSamplesUnclustered`;
const LS_AE_TARGET_INDEX = `${LS_AE_PREFIX}targetIndex`;
const LS_AE_TASK_ID = `${LS_AE_PREFIX}taskId`;
const LS_AE_TASK_STATUS_OBJ = `${LS_AE_PREFIX}taskStatusObj`;
const LS_AE_SHOW_ADVANCED = `${LS_AE_PREFIX}showAdvanced`;
const LS_AE_LIST_FILTER_GROUP = `${LS_AE_PREFIX}listFilterGroup`;
const LS_AE_LIST_PAGE = `${LS_AE_PREFIX}listPage`;
const LS_AE_LIST_ROWS_PER_PAGE = `${LS_AE_PREFIX}listRowsPerPage`;


const AnalyzeErrorsPage: React.FC = () => {
  // Configurable Parameters
  const [groupName, setGroupName] = useState<string>(() => localStorage.getItem(LS_AE_GROUP_NAME) || '');
  const [startTime, setStartTime] = useState<Date | null>(() => {
    const stored = localStorage.getItem(LS_AE_START_TIME);
    return stored ? new Date(stored) : new Date(new Date().getTime() - 24 * 60 * 60 * 1000);
  });
  const [endTime, setEndTime] = useState<Date | null>(() => {
    const stored = localStorage.getItem(LS_AE_END_TIME);
    return stored ? new Date(stored) : new Date();
  });
  const [errorLevels, setErrorLevels] = useState<string>(() => localStorage.getItem(LS_AE_ERROR_LEVELS) || DEFAULT_ERROR_LEVELS_STRING);

  // Advanced Options
  const [showAdvanced, setShowAdvanced] = useState<boolean>(() => JSON.parse(localStorage.getItem(LS_AE_SHOW_ADVANCED) || 'false'));
  const [maxLogsToProcess, setMaxLogsToProcess] = useState<string>(() => localStorage.getItem(LS_AE_MAX_LOGS) || String(DEFAULT_MAX_LOGS_FOR_SUMMARY));
  const [embeddingModelName, setEmbeddingModelName] = useState<string>(() => localStorage.getItem(LS_AE_EMBED_MODEL) || DEFAULT_EMBEDDING_MODEL);
  const [llmModelForSummary, setLlmModelForSummary] = useState<string>(() => localStorage.getItem(LS_AE_LLM_MODEL) || DEFAULT_LLM_FOR_SUMMARY);
  const [dbscanEps, setDbscanEps] = useState<string>(() => localStorage.getItem(LS_AE_DBSCAN_EPS) || String(DEFAULT_DBSCAN_EPS));
  const [dbscanMinSamples, setDbscanMinSamples] = useState<string>(() => localStorage.getItem(LS_AE_DBSCAN_MINS) || String(DEFAULT_DBSCAN_MIN_SAMPLES));
  const [maxSamplesPerCluster, setMaxSamplesPerCluster] = useState<string>(() => localStorage.getItem(LS_AE_MAX_SAMPLES_C) || String(DEFAULT_MAX_SAMPLES_CLUSTER));
  const [maxSamplesUnclustered, setMaxSamplesUnclustered] = useState<string>(() => localStorage.getItem(LS_AE_MAX_SAMPLES_UC) || String(DEFAULT_MAX_SAMPLES_UNCLUSTERED));
  const [targetSummaryIndex, setTargetSummaryIndex] = useState<string>(() => localStorage.getItem(LS_AE_TARGET_INDEX) || DEFAULT_TARGET_SUMMARY_INDEX);

  // Task State
  const [taskId, setTaskId] = useState<string | null>(() => localStorage.getItem(LS_AE_TASK_ID) || null);
  const [taskStatusObj, setTaskStatusObj] = useState<AnalyzeErrorsTaskStatusResponse | null>(() => {
    const stored = localStorage.getItem(LS_AE_TASK_STATUS_OBJ);
    try { return stored ? JSON.parse(stored) : null; } catch (e) { return null; }
  });

  // UI State
  const [allDbGroups, setAllDbGroups] = useState<GroupInfoDetail[]>([]);
  const [loadingRun, setLoadingRun] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageSuccess, setPageSuccess] = useState<string | null>(null);

  const isTaskEffectivelyRunning = taskStatusObj ? !taskStatusObj.completed && !taskStatusObj.error : false;

  // States for listing summaries
  const [listedSummaries, setListedSummaries] = useState<ErrorSummaryListItem[]>([]);
  const [loadingListedSummaries, setLoadingListedSummaries] = useState<boolean>(false);
  const [listError, setListError] = useState<string | null>(null);
  const [listPage, setListPage] = useState<number>(() => parseInt(localStorage.getItem(LS_AE_LIST_PAGE) || '0', 10));
  const [listRowsPerPage, setListRowsPerPage] = useState<number>(() => parseInt(localStorage.getItem(LS_AE_LIST_ROWS_PER_PAGE) || '10', 10));
  const [listTotalRows, setListTotalRows] = useState<number>(0);
  const [listFilterGroup, setListFilterGroup] = useState<string>(() => localStorage.getItem(LS_AE_LIST_FILTER_GROUP) || '');


  // Save to Local Storage Effects
  useEffect(() => { localStorage.setItem(LS_AE_GROUP_NAME, groupName); }, [groupName]);
  useEffect(() => { if(startTime) localStorage.setItem(LS_AE_START_TIME, startTime.toISOString()); }, [startTime]);
  useEffect(() => { if(endTime) localStorage.setItem(LS_AE_END_TIME, endTime.toISOString()); }, [endTime]);
  useEffect(() => { localStorage.setItem(LS_AE_ERROR_LEVELS, errorLevels); }, [errorLevels]);
  useEffect(() => { localStorage.setItem(LS_AE_MAX_LOGS, maxLogsToProcess); }, [maxLogsToProcess]);
  useEffect(() => { localStorage.setItem(LS_AE_EMBED_MODEL, embeddingModelName); }, [embeddingModelName]);
  useEffect(() => { localStorage.setItem(LS_AE_LLM_MODEL, llmModelForSummary); }, [llmModelForSummary]);
  useEffect(() => { localStorage.setItem(LS_AE_DBSCAN_EPS, dbscanEps); }, [dbscanEps]);
  useEffect(() => { localStorage.setItem(LS_AE_DBSCAN_MINS, dbscanMinSamples); }, [dbscanMinSamples]);
  useEffect(() => { localStorage.setItem(LS_AE_MAX_SAMPLES_C, maxSamplesPerCluster); }, [maxSamplesPerCluster]);
  useEffect(() => { localStorage.setItem(LS_AE_MAX_SAMPLES_UC, maxSamplesUnclustered); }, [maxSamplesUnclustered]);
  useEffect(() => { localStorage.setItem(LS_AE_TARGET_INDEX, targetSummaryIndex); }, [targetSummaryIndex]);
  useEffect(() => { localStorage.setItem(LS_AE_SHOW_ADVANCED, JSON.stringify(showAdvanced)); }, [showAdvanced]);

  useEffect(() => {
    if (taskId) localStorage.setItem(LS_AE_TASK_ID, taskId); else localStorage.removeItem(LS_AE_TASK_ID);
  }, [taskId]);
  useEffect(() => {
    if (taskStatusObj) localStorage.setItem(LS_AE_TASK_STATUS_OBJ, JSON.stringify(taskStatusObj)); else localStorage.removeItem(LS_AE_TASK_STATUS_OBJ);
  }, [taskStatusObj]);

  useEffect(() => { localStorage.setItem(LS_AE_LIST_FILTER_GROUP, listFilterGroup); }, [listFilterGroup]);
  useEffect(() => { localStorage.setItem(LS_AE_LIST_PAGE, String(listPage)); }, [listPage]);
  useEffect(() => { localStorage.setItem(LS_AE_LIST_ROWS_PER_PAGE, String(listRowsPerPage)); }, [listRowsPerPage]);


  const fetchGroupsForDropdown = useCallback(async () => {
    try {
      const response = await groupService.listAllGroupsInfo();
      setAllDbGroups(response.groups);
    } catch (error) {
      console.error("Failed to fetch groups for dropdown:", error);
      setPageError("Failed to load available groups for selection.");
    }
  }, []);

  useEffect(() => {
    fetchGroupsForDropdown();
  }, [fetchGroupsForDropdown]);

  const handleRunAnalysis = async () => {
    setPageError(null); setPageSuccess(null);
    setTaskId(null); setTaskStatusObj(null);
    setLoadingRun(true);

    if (!groupName.trim()) {
      setPageError("Please select a group to analyze.");
      setLoadingRun(false);
      return;
    }
    if (!startTime || !endTime) {
        setPageError("Please select a valid start and end time.");
        setLoadingRun(false);
        return;
    }
    if (startTime >= endTime) {
        setPageError("Start time must be before end time.");
        setLoadingRun(false);
        return;
    }

    const params: AnalyzeErrorsRunParams = {
      group_name: groupName.trim(),
      start_time_iso: startTime.toISOString(),
      end_time_iso: endTime.toISOString(),
      error_log_levels: errorLevels.split(',').map(l => l.trim().toLowerCase()).filter(l => l),
      max_logs_to_process: parseInt(maxLogsToProcess, 10) || DEFAULT_MAX_LOGS_FOR_SUMMARY,
      embedding_model_name: embeddingModelName.trim() || DEFAULT_EMBEDDING_MODEL,
      llm_model_for_summary: llmModelForSummary.trim() || DEFAULT_LLM_FOR_SUMMARY,
      dbscan_eps: parseFloat(dbscanEps) || DEFAULT_DBSCAN_EPS,
      dbscan_min_samples: parseInt(dbscanMinSamples, 10) || DEFAULT_DBSCAN_MIN_SAMPLES,
      max_samples_per_cluster: parseInt(maxSamplesPerCluster, 10) || DEFAULT_MAX_SAMPLES_CLUSTER,
      max_samples_unclustered: parseInt(maxSamplesUnclustered, 10) || DEFAULT_MAX_SAMPLES_UNCLUSTERED,
      target_summary_index: targetSummaryIndex.trim() || DEFAULT_TARGET_SUMMARY_INDEX,
    };

    try {
      const response = await analyzeErrorsService.runErrorSummaryAnalysis(params);
      setTaskId(response.task_id);
      setTaskStatusObj({
          task_id: response.task_id, status: 'Pending', completed: false,
          progress_detail: 'Task submitted to API.', error: null, last_updated: new Date().toISOString(),
          result_summary: null, params_used: params
      });
      setPageSuccess(response.message);
    } catch (err: any) {
      const apiErr = err as ApiError;
      const detail = apiErr.detail || 'Failed to start Error Analysis task.';
      setPageError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setLoadingRun(false);
    }
  };

  const fetchCurrentTaskStatus = useCallback(async () => {
    if (!taskId) return;
    try {
      const statusData = await analyzeErrorsService.getErrorAnalysisTaskStatus(taskId);
      setTaskStatusObj(prev => ({...prev, ...statusData}));

      if (statusData.completed || statusData.error) {
        if (statusData.error) {
          setPageError(`Task Error: ${statusData.error}`);
          setPageSuccess(null);
        } else if (statusData.completed) {
          setPageSuccess(`Task ${statusData.task_id.substring(0,8)}: ${statusData.status} - ${statusData.progress_detail || 'Completed.'}`);
          fetchListedSummaries(); // Refresh the list of summaries after a task completes successfully
        }
      }
    } catch (err: any) {
      const apiErr = err as ApiError;
      const detail = apiErr.detail || 'Failed to fetch task status.';
      setPageError(typeof detail === 'string' ? detail : JSON.stringify(detail));
       setTaskStatusObj(prev => prev ? {...prev, error: "Status fetch failed", completed: true, status: "Error"} : null);
    }
  }, [taskId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | undefined;
    if (isTaskEffectivelyRunning && taskId) {
      fetchCurrentTaskStatus();
      intervalId = setInterval(fetchCurrentTaskStatus, 5000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isTaskEffectivelyRunning, taskId, fetchCurrentTaskStatus]);

  const renderClusterDetail = (cluster: ProcessedClusterDetail, index: number) => (
    <Accordion key={cluster.cluster_label || `cluster-${index}`} sx={{mb:1}}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between" sx={{width: '100%'}}>
        <Typography variant="subtitle1" sx={{fontWeight:'bold'}}>
            {cluster.cluster_label} ({cluster.total_logs_in_cluster} logs)
        </Typography>
        {cluster.summary_generated ? <Chip icon={<CheckCircleOutlineIcon />} label="Summary Generated" color="success" size="small"/> :
                                     <Chip icon={<ErrorOutlineIcon />} label="No Summary" color="warning" size="small"/>}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        {cluster.summary_output ? (
          <>
            <Typography variant="body2"><strong>Time Range:</strong> {cluster.cluster_time_range_start || 'N/A'} to {cluster.cluster_time_range_end || 'N/A'}</Typography>
            <Typography variant="body2" sx={{mt:0.5}}><strong>LLM Summary:</strong> {cluster.summary_output.summary}</Typography>
            <Typography variant="body2" sx={{mt:0.5}}><strong>Potential Cause:</strong> {cluster.summary_output.potential_cause || 'Undetermined'}</Typography>
            <Typography variant="body2" sx={{mt:0.5}}><strong>Keywords:</strong> {cluster.summary_output.keywords.join(', ')}</Typography>
            <Typography variant="body2" sx={{fontStyle: 'italic', mt:1}}>
              <strong>Representative Log:</strong> "{cluster.summary_output.representative_log_line || 'N/A'}"
            </Typography>
             {cluster.summary_document_id_es && <Typography variant="caption" display="block" sx={{mt:1}}>ES Doc ID: {cluster.summary_document_id_es}</Typography>}
          </>
        ) : (
          <Typography variant="body2">Summary details not available for this cluster (generation may have failed or is pending).</Typography>
        )}
        {cluster.sampled_log_messages_used && cluster.sampled_log_messages_used.length > 0 && (
            <Box sx={{mt:1}}>
                <Typography variant="caption">Samples used for summary ({cluster.sampled_log_messages_used.length}):</Typography>
                <List dense sx={{maxHeight: '100px', overflowY:'auto', fontSize:'0.75rem', bgcolor: 'action.hover', borderRadius: 1, p:0.5}}>
                    {cluster.sampled_log_messages_used.map((log, idx) => <ListItem key={idx} sx={{py:0}}><ListItemText primaryTypographyProps={{variant:'caption'}} primary={`- ${log.substring(0,150)}...`} /></ListItem>)}
                </List>
            </Box>
        )}
      </AccordionDetails>
    </Accordion>
  );

  // Fetching and displaying previously generated summaries
  const fetchListedSummaries = useCallback(async (showLoadingSpinner: boolean = true) => {
    if(showLoadingSpinner) setLoadingListedSummaries(true);
    setListError(null);
    try {
      const params: any = {
        limit: listRowsPerPage,
        offset: listPage * listRowsPerPage,
        sort_by: "generation_timestamp", // Default sort
        sort_order: "desc",
      };
      if (listFilterGroup.trim()) {
        params.group_name = listFilterGroup.trim();
      }

      const response = await analyzeErrorsService.listGeneratedErrorSummaries(params);
      setListedSummaries(response.summaries);
      setListTotalRows(response.total);
    } catch (err) {
      const apiError = err as ApiError;
      const detail = apiError.detail || 'Failed to fetch previously generated summaries.';
      setListError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      if(showLoadingSpinner) setLoadingListedSummaries(false);
    }
  }, [listPage, listRowsPerPage, listFilterGroup]);

  useEffect(() => {
    fetchListedSummaries();
  }, [fetchListedSummaries]);

  const handleChangeListPage = (event: unknown, newPage: number) => {
    setListPage(newPage);
  };

  const handleChangeListRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setListRowsPerPage(parseInt(event.target.value, 10));
    setListPage(0);
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Typography variant="h4" gutterBottom component="h1" sx={{ textAlign: 'center' }}>
        Error Log Summarization
      </Typography>

      {pageError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setPageError(null)}>{pageError}</Alert>}
      {pageSuccess && !loadingRun && !isTaskEffectivelyRunning && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setPageSuccess(null)}>{pageSuccess}</Alert>
      )}

      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>Configuration</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <TextField
              select
              label="Target Group"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              fullWidth
              disabled={loadingRun || isTaskEffectivelyRunning}
              SelectProps={{ native: true }}
              InputLabelProps={{ shrink: true }}
              variant="outlined"
            >
              <option value="">-- Select Log Group --</option>
              {allDbGroups.map(g => <option key={`errsum-group-${g.group_name}`} value={g.group_name}>{g.group_name}</option>)}
            </TextField>
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              label="Error Levels (comma-separated)"
              value={errorLevels}
              onChange={(e) => setErrorLevels(e.target.value)}
              fullWidth
              helperText="e.g., error,critical,fatal,warn"
              disabled={loadingRun || isTaskEffectivelyRunning}
              variant="outlined"
            />
          </Grid>
          <Grid item xs={12} md={6}>
             <DateTimePicker
                label="Start Time (UTC)"
                value={startTime}
                onChange={(newValue) => setStartTime(newValue)}
                ampm={false}
                format="yyyy-MM-dd HH:mm:ss"
                disabled={loadingRun || isTaskEffectivelyRunning}
                slotProps={{ textField: { fullWidth: true, variant: 'outlined', helperText:"Logs are typically in UTC" } }}
            />
          </Grid>
          <Grid item xs={12} md={6}>
             <DateTimePicker
                label="End Time (UTC)"
                value={endTime}
                onChange={(newValue) => setEndTime(newValue)}
                ampm={false}
                format="yyyy-MM-dd HH:mm:ss"
                disabled={loadingRun || isTaskEffectivelyRunning}
                slotProps={{ textField: { fullWidth: true, variant: 'outlined', helperText:"Logs are typically in UTC" } }}
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={<Switch checked={showAdvanced} onChange={(e) => setShowAdvanced(e.target.checked)} />}
              label="Show Advanced Options"
            />
          </Grid>

        <Collapse in={showAdvanced} timeout="auto" unmountOnExit sx={{width: '100%'}}>
          <Grid container spacing={2} sx={{pl:2, pt:1}}>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="Max Logs to Process" type="number" value={maxLogsToProcess} onChange={e => setMaxLogsToProcess(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning} />
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="Embedding Model" value={embeddingModelName} onChange={e => setEmbeddingModelName(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning}/>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="LLM for Summaries" value={llmModelForSummary} onChange={e => setLlmModelForSummary(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning}/>
            </Grid>
             <Grid item xs={12} md={6} lg={4}>
                <TextField label="Target Summary Index" value={targetSummaryIndex} onChange={e => setTargetSummaryIndex(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning}/>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="DBSCAN Epsilon (eps)" type="number" value={dbscanEps} onChange={e => setDbscanEps(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning} InputProps={{inputProps: {step: "0.01"}}}/>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="DBSCAN Min Samples" type="number" value={dbscanMinSamples} onChange={e => setDbscanMinSamples(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning} InputProps={{inputProps: {min:1}}}/>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="Max Samples per Cluster (LLM)" type="number" value={maxSamplesPerCluster} onChange={e => setMaxSamplesPerCluster(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning} InputProps={{inputProps: {min:1}}}/>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
                <TextField label="Max Samples Unclustered (LLM)" type="number" value={maxSamplesUnclustered} onChange={e => setMaxSamplesUnclustered(e.target.value)} fullWidth variant="outlined" disabled={loadingRun || isTaskEffectivelyRunning} InputProps={{inputProps: {min:1}}}/>
            </Grid>
          </Grid>
        </Collapse>

          <Grid item xs={12} sx={{ textAlign: 'center', mt:1 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleRunAnalysis}
              disabled={loadingRun || isTaskEffectivelyRunning || !groupName || !startTime || !endTime}
              startIcon={(loadingRun || isTaskEffectivelyRunning) ? <CircularProgress size={20} color="inherit" /> : <ScienceIcon />}
              size="large"
            >
              {isTaskEffectivelyRunning ? `Analysis Running... (${taskStatusObj?.status || 'Connecting'})` : 'Run Error Analysis'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {taskId && taskStatusObj && (
        <Paper elevation={2} sx={{ p: 2, mb: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
                Analysis Task (ID: <Chip label={taskId.substring(0,8)} size="small" color="secondary"/>)
            </Typography>
            <Tooltip title="Refresh task status">
                <IconButton onClick={fetchCurrentTaskStatus} disabled={isTaskEffectivelyRunning && !taskStatusObj?.error}>
                    <RefreshIcon />
                </IconButton>
            </Tooltip>
          </Stack>
          <LinearProgress
            variant={taskStatusObj.completed || !isTaskEffectivelyRunning ? 'determinate' : 'indeterminate'}
            value={taskStatusObj.completed ? 100 : (taskStatusObj.status.toLowerCase().includes("summarizing") ? 75 : taskStatusObj.status.toLowerCase().includes("clustering") ? 60 : taskStatusObj.status.toLowerCase().includes("embedding") ? 40 : taskStatusObj.status.toLowerCase().includes("fetching") ? 20 : 10)}
            sx={{ my: 1 }}
          />
          <Typography>Status: <Chip label={taskStatusObj.status || 'N/A'} size="small" color={taskStatusObj.status === 'Completed' || taskStatusObj.status.startsWith('completed') ? 'success' : taskStatusObj.status === 'Failed' ? 'error' : 'info'} /> </Typography>
          <Typography variant="body2">Details: {taskStatusObj.progress_detail || 'N/A'}</Typography>
          {taskStatusObj.error && <Alert severity="error" sx={{ mt: 1 }}>Task Error: {taskStatusObj.error}</Alert>}

          {taskStatusObj.completed && !taskStatusObj.error && taskStatusObj.result_summary && (
             <Accordion sx={{mt:2}} defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1" sx={{fontWeight: 'bold'}}>Analysis Result Summary</Typography>
                </AccordionSummary>
                <AccordionDetails sx={{maxHeight: '500px', overflowY: 'auto'}}>
                    <Typography variant="body2" gutterBottom>Agent Final Status: {taskStatusObj.result_summary.agent_status || "N/A"}</Typography>
                    <Typography variant="body2" gutterBottom>Raw Error Logs Fetched: {taskStatusObj.result_summary.raw_logs_fetched_count ?? "N/A"}</Typography>
                    <Typography variant="body2" gutterBottom>Total Summaries Stored: {taskStatusObj.result_summary.final_summary_ids_count ?? "N/A"}</Typography>
                    {taskStatusObj.result_summary.errors_during_run && taskStatusObj.result_summary.errors_during_run.length > 0 && (
                         <Alert severity="warning" sx={{my:1}}>
                            Encountered {taskStatusObj.result_summary.errors_during_run.length} issues during processing:
                            <List dense disablePadding>{taskStatusObj.result_summary.errors_during_run.map((e,i)=><ListItem key={i} sx={{py:0}}><ListItemText primaryTypographyProps={{variant:'caption'}} primary={`- ${e}`}/></ListItem>)}</List>
                         </Alert>
                    )}
                    <Divider sx={{my:2}}><Chip label="Processed Cluster Details" size="small"/></Divider>
                    {taskStatusObj.result_summary.processed_cluster_details && taskStatusObj.result_summary.processed_cluster_details.length > 0
                        ? taskStatusObj.result_summary.processed_cluster_details.map(renderClusterDetail)
                        : <Typography variant="body2" sx={{textAlign: 'center', my:2}}>No cluster details available.</Typography>
                    }
                </AccordionDetails>
             </Accordion>
          )}
        </Paper>
      )}
        <Paper elevation={2} sx={{ p: 2, mt: 3 }}>
             <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{mb:2}}>
                <Typography variant="h5" gutterBottom>
                Previously Generated Summaries
                </Typography>
                <Tooltip title="Refresh Summaries List">
                    <IconButton onClick={() => fetchListedSummaries()} disabled={loadingListedSummaries}>
                        <RefreshIcon />
                    </IconButton>
                </Tooltip>
            </Stack>
            <TextField // Renamed from MuiTextField back to TextField as it's standard
                label="Filter by Group Name"
                variant="outlined"
                size="small"
                value={listFilterGroup}
                onChange={(e) => {
                    setListFilterGroup(e.target.value);
                    setListPage(0);
                }}
                sx={{ mb: 2, width: '300px' }}
            />

            {listError && <Alert severity="error" sx={{mb:1}}>{listError}</Alert>}

            {loadingListedSummaries ? (
                <CircularProgress sx={{display: 'block', margin: '20px auto'}}/>
            ) : listedSummaries.length === 0 && !listError ? (
                <Alert severity="info">No previously generated summaries found matching your criteria.</Alert>
            ) : (
                <>
                <TableContainer component={Paper} variant="outlined">
                    <Table size="small" aria-label="previously generated summaries table">
                    <TableHead>
                        <TableRow>
                        <TableCell sx={{fontWeight:'bold'}}>Group</TableCell>
                        <TableCell sx={{fontWeight:'bold'}}>Cluster</TableCell>
                        <TableCell sx={{fontWeight:'bold'}}>Summary</TableCell>
                        <TableCell sx={{fontWeight:'bold'}}>Keywords</TableCell>
                        <TableCell sx={{fontWeight:'bold'}}>Generated At</TableCell>
                        <TableCell sx={{fontWeight:'bold'}} align="right">Samples/Total</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {listedSummaries.map((summary) => (
                        <TableRow hover key={summary.summary_id}>
                            <TableCell><Chip label={summary.group_name} size="small" /></TableCell>
                            <TableCell><Chip label={summary.cluster_id} size="small" variant="outlined" /></TableCell>
                            <TableCell>
                                <Tooltip title={summary.summary_text}>
                                    <Typography variant="body2" noWrap sx={{maxWidth: '250px'}}>
                                        {summary.summary_text}
                                    </Typography>
                                </Tooltip>
                            </TableCell>
                            <TableCell>
                                <Tooltip title={summary.keywords.join(', ')}>
                                    <Typography variant="body2" noWrap sx={{maxWidth: '150px'}}>
                                        {summary.keywords.join(', ')}
                                    </Typography>
                                </Tooltip>
                            </TableCell>
                            <TableCell>{new Date(summary.generation_timestamp).toLocaleString()}</TableCell>
                            <TableCell align="right">{summary.sample_log_count}/{summary.total_logs_in_cluster}</TableCell>
                        </TableRow>
                        ))}
                    </TableBody>
                    </Table>
                </TableContainer>
                <TablePagination
                    rowsPerPageOptions={[5, 10, 25, 50]}
                    component="div"
                    count={listTotalRows}
                    rowsPerPage={listRowsPerPage}
                    page={listPage}
                    onPageChange={handleChangeListPage}
                    onRowsPerPageChange={handleChangeListRowsPerPage}
                />
                </>
            )}
        </Paper>
    </Container>
    </LocalizationProvider>
  );
};

export default AnalyzeErrorsPage;

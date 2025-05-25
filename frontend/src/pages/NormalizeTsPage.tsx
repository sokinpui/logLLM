// frontend/src/pages/NormalizeTsPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Typography, Grid, TextField, Button, Paper, Box, CircularProgress,
  Alert, Switch, FormControlLabel, Divider, Chip, Accordion, AccordionSummary,
  AccordionDetails, Tooltip, IconButton, Select, MenuItem, InputLabel, FormControl,
  Card, CardContent, LinearProgress, Stack
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

import * as normalizeTsService from '../services/normalizeTsService';
import * as groupService from '../services/groupService'; // To fetch groups
import type { ApiError } from '../types/api';
import type { GroupInfoDetail } from '../types/group';
import type {
  NormalizeTsRunRequest,
  NormalizeTsTaskStatusResponse,
  NormalizeTsTaskGroupResult
} from '../types/normalizeTs';

// Local Storage Keys
const LS_NORMTS_PREFIX = 'logllm_normalizets_';
const LS_NORMTS_ACTION = `${LS_NORMTS_PREFIX}action`;
const LS_NORMTS_GROUP_NAME = `${LS_NORMTS_PREFIX}groupName`;
const LS_NORMTS_ALL_GROUPS = `${LS_NORMTS_PREFIX}allGroups`;
const LS_NORMTS_LIMIT = `${LS_NORMTS_PREFIX}limitPerGroup`;
const LS_NORMTS_BATCH_SIZE = `${LS_NORMTS_PREFIX}batchSize`;
const LS_NORMTS_CONFIRM_DELETE = `${LS_NORMTS_PREFIX}confirmDelete`;
const LS_NORMTS_TASK_ID = `${LS_NORMTS_PREFIX}taskId`;
const LS_NORMTS_TASK_STATUS_OBJ = `${LS_NORMTS_PREFIX}taskStatusObj`;

const DEFAULT_BATCH_SIZE = 5000; // Match backend default

const NormalizeTsPage: React.FC = () => {
  const [action, setAction] = useState<'normalize' | 'remove_field'>(() => (localStorage.getItem(LS_NORMTS_ACTION) as 'normalize' | 'remove_field') || 'normalize');
  const [groupName, setGroupName] = useState<string>(() => localStorage.getItem(LS_NORMTS_GROUP_NAME) || '');
  const [allGroups, setAllGroups] = useState<boolean>(() => JSON.parse(localStorage.getItem(LS_NORMTS_ALL_GROUPS) || 'true'));
  const [limitPerGroup, setLimitPerGroup] = useState<string>(() => localStorage.getItem(LS_NORMTS_LIMIT) || '');
  const [batchSize, setBatchSize] = useState<number>(() => parseInt(localStorage.getItem(LS_NORMTS_BATCH_SIZE) || String(DEFAULT_BATCH_SIZE), 10));
  const [confirmDelete, setConfirmDelete] = useState<boolean>(() => JSON.parse(localStorage.getItem(LS_NORMTS_CONFIRM_DELETE) || 'false'));

  const [taskId, setTaskId] = useState<string | null>(() => localStorage.getItem(LS_NORMTS_TASK_ID) || null);
  const [taskStatusObj, setTaskStatusObj] = useState<NormalizeTsTaskStatusResponse | null>(() => {
    const stored = localStorage.getItem(LS_NORMTS_TASK_STATUS_OBJ);
    try { return stored ? JSON.parse(stored) : null; } catch (e) { return null; }
  });

  const [allDbGroups, setAllDbGroups] = useState<GroupInfoDetail[]>([]);
  const [loadingRun, setLoadingRun] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageSuccess, setPageSuccess] = useState<string | null>(null);

  const isTaskEffectivelyRunning = taskStatusObj ? !taskStatusObj.completed && !taskStatusObj.error : false;

  // Save to Local Storage Effects
  useEffect(() => { localStorage.setItem(LS_NORMTS_ACTION, action); }, [action]);
  useEffect(() => { localStorage.setItem(LS_NORMTS_GROUP_NAME, groupName); }, [groupName]);
  useEffect(() => { localStorage.setItem(LS_NORMTS_ALL_GROUPS, JSON.stringify(allGroups)); }, [allGroups]);
  useEffect(() => { localStorage.setItem(LS_NORMTS_LIMIT, limitPerGroup); }, [limitPerGroup]);
  useEffect(() => { localStorage.setItem(LS_NORMTS_BATCH_SIZE, String(batchSize)); }, [batchSize]);
  useEffect(() => { localStorage.setItem(LS_NORMTS_CONFIRM_DELETE, JSON.stringify(confirmDelete)); }, [confirmDelete]);
  useEffect(() => {
    if (taskId) localStorage.setItem(LS_NORMTS_TASK_ID, taskId);
    else localStorage.removeItem(LS_NORMTS_TASK_ID);
  }, [taskId]);
  useEffect(() => {
    if (taskStatusObj) localStorage.setItem(LS_NORMTS_TASK_STATUS_OBJ, JSON.stringify(taskStatusObj));
    else localStorage.removeItem(LS_NORMTS_TASK_STATUS_OBJ);
  }, [taskStatusObj]);

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

  const handleRunTask = async () => {
    setPageError(null); setPageSuccess(null);
    setTaskId(null); setTaskStatusObj(null);
    setLoadingRun(true);

    if (!allGroups && !groupName.trim()) {
      setPageError("Please select a group or 'All Groups'.");
      setLoadingRun(false);
      return;
    }

    if (action === 'remove_field' && !confirmDelete) {
      if (!window.confirm("Are you sure you want to remove the '@timestamp' field from the selected parsed log indices? This action modifies data.")) {
        setLoadingRun(false);
        return;
      }
    }

    const params: NormalizeTsRunRequest = {
      action,
      all_groups: allGroups,
      group_name: allGroups ? null : groupName.trim() || null,
      limit_per_group: action === 'normalize' && limitPerGroup.trim() !== '' ? parseInt(limitPerGroup, 10) : null,
      batch_size: batchSize,
      confirm_delete: action === 'remove_field' ? true : undefined, // Send true if confirmed by UI/window.confirm
    };

    try {
      const response = await normalizeTsService.runNormalizeTsTask(params);
      const extractedTaskIdMatch = response.message.match(/Task ID: ([a-f0-9-]+)/i);
      const extractedTaskId = extractedTaskIdMatch ? extractedTaskIdMatch[1] : null;

      if (extractedTaskId) {
        setTaskId(extractedTaskId);
        setTaskStatusObj({
          task_id: extractedTaskId, status: 'Pending', completed: false,
          progress_detail: 'Task initiated by API.', error: null, last_updated: new Date().toISOString(), result_summary: null
        });
        setPageSuccess(response.message);
      } else {
        setPageError("Task initiated but no Task ID received in the API response message.");
        setTaskStatusObj(null); // Clear any partial task state
      }
    } catch (err: any) {
      const apiErr = err as ApiError;
      const detail = apiErr.detail || 'Failed to start Timestamp Normalizer task.';
      setPageError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setLoadingRun(false);
    }
  };

  const fetchCurrentTaskStatus = useCallback(async () => {
    if (!taskId) return;
    try {
      const statusData = await normalizeTsService.getNormalizeTsTaskStatus(taskId);
      setTaskStatusObj(statusData);
      if (statusData.completed || statusData.error) {
        if (statusData.error) {
          setPageError(`Task Error: ${statusData.error}`);
          setPageSuccess(null);
        } else {
          setPageSuccess(`Task ${statusData.task_id.substring(0,8)} Completed: ${statusData.status} - ${statusData.progress_detail || ''}`);
        }
      }
    } catch (err: any) {
      const apiErr = err as ApiError;
      const detail = apiErr.detail || 'Failed to fetch task status.';
      setPageError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setTaskStatusObj(prev => prev ? {...prev, error: "Status fetch failed", completed: true} : {task_id: taskId, status: "Error", error: "Status fetch failed", completed:true, result_summary: null, last_updated: new Date().toISOString(), progress_detail: null});
    }
  }, [taskId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | undefined;
    if (isTaskEffectivelyRunning && taskId) {
      fetchCurrentTaskStatus(); // Initial fetch
      intervalId = setInterval(fetchCurrentTaskStatus, 5000); // Poll every 5 seconds
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isTaskEffectivelyRunning, taskId, fetchCurrentTaskStatus]);


  const renderGroupResult = (groupName: string, result: NormalizeTsTaskGroupResult) => (
    <Card key={groupName} variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">{groupName}</Typography>
          <Chip
            label={result.status_this_run}
            size="small"
            color={result.status_this_run.includes('completed') ? 'success' : result.status_this_run.includes('failed') ? 'error' : 'info'}
          />
        </Stack>
        {result.error_message_this_run && (
          <Alert severity="error" sx={{ mt: 1, fontSize: '0.8rem' }}>{result.error_message_this_run}</Alert>
        )}
        <Grid container spacing={1} sx={{ mt: 1 }}>
          <Grid item xs={6} sm={3}>
            <Typography variant="body2">Scanned: {result.documents_scanned_this_run}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="body2">Updated: {result.documents_updated_this_run}</Typography>
          </Grid>
          {action === 'normalize' && (
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color={result.timestamp_normalization_errors_this_run > 0 ? 'error' : 'inherit'}>
                Normalization Errors: {result.timestamp_normalization_errors_this_run}
              </Typography>
            </Grid>
          )}
        </Grid>
      </CardContent>
    </Card>
  );


  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h4" gutterBottom component="h1" sx={{ textAlign: 'center' }}>
        Timestamp Normalizer
      </Typography>

      {pageError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setPageError(null)}>{pageError}</Alert>}
      {pageSuccess && !loadingRun && !isTaskEffectivelyRunning && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setPageSuccess(null)}>{pageSuccess}</Alert>}

      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>Configuration</Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel id="action-select-label">Action</InputLabel>
              <Select
                labelId="action-select-label"
                value={action}
                label="Action"
                onChange={(e) => setAction(e.target.value as 'normalize' | 'remove_field')}
                disabled={loadingRun || isTaskEffectivelyRunning}
              >
                <MenuItem value="normalize">Normalize Timestamps</MenuItem>
                <MenuItem value="remove_field">Delete @timestamp Field</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6}>
             <FormControlLabel
              control={<Switch checked={allGroups} onChange={(e) => {setAllGroups(e.target.checked); if(e.target.checked) setGroupName('');}} disabled={loadingRun || isTaskEffectivelyRunning} />}
              label="Process All Groups"
            />
          </Grid>
          {!allGroups && (
            <Grid item xs={12}>
              <TextField
                select
                label="Target Group"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                fullWidth
                disabled={allGroups || loadingRun || isTaskEffectivelyRunning}
                SelectProps={{ native: true }}
                InputLabelProps={{ shrink: true }}
              >
                <option value="">-- Select Specific Group --</option>
                {allDbGroups.map(g => <option key={`normts-${g.group_name}`} value={g.group_name}>{g.group_name}</option>)}
              </TextField>
            </Grid>
          )}
          {action === 'normalize' && (
            <Grid item xs={12} sm={6}>
              <TextField
                label="Limit per Group (optional)"
                type="number"
                value={limitPerGroup}
                onChange={(e) => setLimitPerGroup(e.target.value)}
                fullWidth
                helperText="For testing: max docs per group"
                disabled={loadingRun || isTaskEffectivelyRunning}
                InputProps={{ inputProps: { min: 1 } }}
              />
            </Grid>
          )}
          <Grid item xs={12} sm={action === 'normalize' ? 6 : 12}>
            <TextField
              label="Batch Size"
              type="number"
              value={batchSize}
              onChange={(e) => setBatchSize(Math.max(1, parseInt(e.target.value,10) || DEFAULT_BATCH_SIZE))}
              fullWidth
              disabled={loadingRun || isTaskEffectivelyRunning}
              InputProps={{ inputProps: { min: 1 } }}
            />
          </Grid>

          {action === 'remove_field' && (
            <Grid item xs={12}>
              <FormControlLabel
                control={<Switch checked={confirmDelete} onChange={(e) => setConfirmDelete(e.target.checked)} disabled={loadingRun || isTaskEffectivelyRunning}/>}
                label="Confirm Deletion (Warning: Modifies data)"
                sx={{color: theme => confirmDelete ? theme.palette.error.main : 'inherit'}}
              />
            </Grid>
          )}

          <Grid item xs={12} sx={{ textAlign: 'center' }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleRunTask}
              disabled={loadingRun || isTaskEffectivelyRunning || (!allGroups && !groupName)}
              startIcon={(loadingRun || isTaskEffectivelyRunning) ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />}
              size="large"
            >
              {isTaskEffectivelyRunning ? `Task Running... (${taskStatusObj?.status || 'Connecting'})` : `Run ${action === 'normalize' ? 'Normalization' : 'Deletion'}`}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {taskId && taskStatusObj && (
        <Paper elevation={2} sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6">Task Progress (ID: <Chip label={taskId.substring(0,8)} size="small" color="secondary"/>)</Typography>
          <LinearProgress
            variant={taskStatusObj.completed || !isTaskEffectivelyRunning ? 'determinate' : 'indeterminate'}
            value={taskStatusObj.completed ? 100 : (taskStatusObj.status === "Running" ? 50 : 10)}
            sx={{ my: 1 }}
          />
          <Typography>Status: <Chip label={taskStatusObj.status || 'N/A'} size="small" color={taskStatusObj.status === 'Completed' ? 'success' : taskStatusObj.status === 'Error' ? 'error' : 'info'} /> </Typography>
          <Typography variant="body2">Details: {taskStatusObj.progress_detail || 'N/A'}</Typography>
          {taskStatusObj.error && <Alert severity="error" sx={{ mt: 1 }}>Task Error: {taskStatusObj.error}</Alert>}

          {taskStatusObj.completed && !taskStatusObj.error && taskStatusObj.result_summary && (
             <Accordion sx={{mt:2}} defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle1" sx={{fontWeight: 'bold'}}>Task Execution Summary</Typography>
                </AccordionSummary>
                <AccordionDetails sx={{maxHeight: '400px', overflowY: 'auto'}}>
                    {Object.entries(taskStatusObj.result_summary).map(([grpName, grpData]) =>
                        renderGroupResult(grpName, grpData as NormalizeTsTaskGroupResult)
                    )}
                </AccordionDetails>
             </Accordion>
          )}
        </Paper>
      )}
    </Container>
  );
};

export default NormalizeTsPage;

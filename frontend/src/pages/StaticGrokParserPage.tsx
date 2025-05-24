// frontend/src/pages/StaticGrokParserPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Typography, Grid, TextField, Button, Paper, Box, CircularProgress,
  Alert, Switch, FormControlLabel, Divider, Chip, Accordion, AccordionSummary,
  AccordionDetails, Tooltip, IconButton, // TextareaAutosize removed
  TableContainer, Table,
  TableHead, TableRow, TableCell, TableBody, Link as MuiLink,
  useTheme,
  MenuItem
} from '@mui/material';
import { lighten } from '@mui/material/styles';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RefreshIcon from '@mui/icons-material/Refresh';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
// SaveIcon, FileUploadIcon, FileDownloadIcon removed as editor is gone
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';


import * as staticGrokService from '../services/staticGrokParseService';
import type { ApiError } from '../types/api';
import type { GroupInfoDetail } from '../types/group';
import * as groupService from '../services/groupService';

// Local Storage Keys
const LS_SGROK_PREFIX = 'logllm_staticgrok_';
const LS_SGROK_RUN_GROUP_NAME = `${LS_SGROK_PREFIX}runGroupName`;
const LS_SGROK_RUN_ALL_GROUPS = `${LS_SGROK_PREFIX}runAllGroups`;
const LS_SGROK_CLEAR_PREVIOUS = `${LS_SGROK_PREFIX}clearPrevious`;
// const LS_SGROK_PATTERNS_CONTENT = `${LS_SGROK_PREFIX}patternsContent`; // REMOVED
const LS_SGROK_PATTERNS_FILE_PATH = `${LS_SGROK_PREFIX}patternsFilePath`;
// const LS_SGROK_USE_SERVER_PATH = `${LS_SGROK_PREFIX}useServerPath`; // REMOVED
const LS_SGROK_SERVER_PATH_CONFIRMED = `${LS_SGROK_PREFIX}serverPathConfirmed`;
const LS_SGROK_FILTER_STATUS_GROUP = `${LS_SGROK_PREFIX}filterStatusGroup`;
const LS_SGROK_DELETE_GROUP_NAME = `${LS_SGROK_PREFIX}deleteGroupName`;
const LS_SGROK_DELETE_ALL_GROUPS = `${LS_SGROK_PREFIX}deleteAllGroups`;
const LS_SGROK_TASK_ID = `${LS_SGROK_PREFIX}taskId`;
const LS_SGROK_TASK_STATUS_OBJ = `${LS_SGROK_PREFIX}taskStatusObj`;


const StaticGrokParserPage: React.FC = () => {
  const theme = useTheme();

  const [runGroupName, setRunGroupName] = useState<string>(() => localStorage.getItem(LS_SGROK_RUN_GROUP_NAME) || '');
  const [runAllGroups, setRunAllGroups] = useState<boolean>(() => JSON.parse(localStorage.getItem(LS_SGROK_RUN_ALL_GROUPS) || 'true'));
  const [clearPrevious, setClearPrevious] = useState<boolean>(() => JSON.parse(localStorage.getItem(LS_SGROK_CLEAR_PREVIOUS) || 'false'));

  // Removed state for grokPatternsContent, grokPatternsFilename, isPatternsModified
  const [grokPatternsFilePathOnServer, setGrokPatternsFilePathOnServer] = useState<string>(() => localStorage.getItem(LS_SGROK_PATTERNS_FILE_PATH) || '');
  // useServerPathForPatterns removed, path is now always primary
  const [serverPathConfirmed, setServerPathConfirmed] = useState<boolean>(() => {
    const storedPath = localStorage.getItem(LS_SGROK_PATTERNS_FILE_PATH) || '';
    const storedConfirmed = JSON.parse(localStorage.getItem(LS_SGROK_SERVER_PATH_CONFIRMED) || 'false');
    return storedPath.trim() !== '' && storedConfirmed;
  });

  const [taskId, setTaskId] = useState<string | null>(() => localStorage.getItem(LS_SGROK_TASK_ID) || null);
  const [taskStatusObj, setTaskStatusObj] = useState<staticGrokService.StaticGrokTaskStatus | null>(() => {
      const stored = localStorage.getItem(LS_SGROK_TASK_STATUS_OBJ);
      try { return stored ? JSON.parse(stored) : null; } catch (e) { return null;}
  });

  const taskStatus = taskStatusObj?.status || null;
  const taskProgressDetail = taskStatusObj?.progress_detail || null;
  const taskError = taskStatusObj?.error || null;
  const isTaskRunning = taskStatusObj ? !taskStatusObj.completed && !taskStatusObj.error : false;
  const taskResultSummary = taskStatusObj?.result_summary || null;


  const [statusList, setStatusList] = useState<staticGrokService.StaticGrokParseStatusItem[]>([]);
  const [filterStatusGroup, setFilterStatusGroup] = useState<string>(() => localStorage.getItem(LS_SGROK_FILTER_STATUS_GROUP) || '');

  const [deleteGroupName, setDeleteGroupName] = useState<string>(() => localStorage.getItem(LS_SGROK_DELETE_GROUP_NAME) || '');
  const [deleteAllGroupsData, setDeleteAllGroupsData] = useState<boolean>(() => JSON.parse(localStorage.getItem(LS_SGROK_DELETE_ALL_GROUPS) || 'false'));

  const [allDbGroups, setAllDbGroups] = useState<GroupInfoDetail[]>([]);

  const [loadingRun, setLoadingRun] = useState<boolean>(false);
  const [loadingStatusList, setLoadingStatusList] = useState<boolean>(false);
  const [loadingDelete, setLoadingDelete] = useState<boolean>(false);
  // loadingPatterns removed
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageSuccess, setPageSuccess] = useState<string | null>(null);

  // Save to Local Storage Effects
  useEffect(() => { localStorage.setItem(LS_SGROK_RUN_GROUP_NAME, runGroupName); }, [runGroupName]);
  useEffect(() => { localStorage.setItem(LS_SGROK_RUN_ALL_GROUPS, JSON.stringify(runAllGroups)); }, [runAllGroups]);
  useEffect(() => { localStorage.setItem(LS_SGROK_CLEAR_PREVIOUS, JSON.stringify(clearPrevious)); }, [clearPrevious]);
  // grokPatternsContent useEffect removed
  useEffect(() => {
    localStorage.setItem(LS_SGROK_PATTERNS_FILE_PATH, grokPatternsFilePathOnServer);
    if (!grokPatternsFilePathOnServer.trim()) {
        setServerPathConfirmed(false);
    }
  }, [grokPatternsFilePathOnServer]);
  // useServerPathForPatterns useEffect removed
  useEffect(() => { localStorage.setItem(LS_SGROK_SERVER_PATH_CONFIRMED, JSON.stringify(serverPathConfirmed));}, [serverPathConfirmed]);
  useEffect(() => { localStorage.setItem(LS_SGROK_FILTER_STATUS_GROUP, filterStatusGroup); }, [filterStatusGroup]);
  useEffect(() => { localStorage.setItem(LS_SGROK_DELETE_GROUP_NAME, deleteGroupName); }, [deleteGroupName]);
  useEffect(() => { localStorage.setItem(LS_SGROK_DELETE_ALL_GROUPS, JSON.stringify(deleteAllGroupsData)); }, [deleteAllGroupsData]);

  useEffect(() => {
    if (taskId) localStorage.setItem(LS_SGROK_TASK_ID, taskId);
    else localStorage.removeItem(LS_SGROK_TASK_ID);
  }, [taskId]);

  useEffect(() => {
    if (taskStatusObj) localStorage.setItem(LS_SGROK_TASK_STATUS_OBJ, JSON.stringify(taskStatusObj));
    else localStorage.removeItem(LS_SGROK_TASK_STATUS_OBJ);
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

  // fetchGrokPatterns (for editor content) removed

  useEffect(() => {
    fetchGroupsForDropdown();
    // No need to fetch patterns for editor anymore
  }, [fetchGroupsForDropdown]);


  const handleRunParser = async () => {
    setPageError(null); setPageSuccess(null);
    setTaskId(null); setTaskStatusObj(null);
    setLoadingRun(true);

    if (!grokPatternsFilePathOnServer.trim()) {
        setPageError("Please specify the Grok patterns file path on the server.");
        setLoadingRun(false);
        return;
    }
    if (!serverPathConfirmed) {
       setPageError("Server path is not confirmed. Please click 'Confirm Path'.");
       setLoadingRun(false);
       return;
    }

    const params: staticGrokService.StaticGrokRunRequest = {
      all_groups: runAllGroups,
      group_name: runAllGroups ? null : runGroupName.trim() || null,
      clear_previous_results: clearPrevious,
      grok_patterns_file_path_on_server: grokPatternsFilePathOnServer.trim(),
      // grok_patterns_file_content is no longer sent from this UI
    };

    try {
      const response = await staticGrokService.runStaticGrokParser(params);
      setTaskId(response.task_id);
      setTaskStatusObj({
          task_id: response.task_id, status: 'Pending', completed: false,
          progress_detail: 'Task initiated by API.', error: null, last_updated: new Date().toISOString(), result_summary: null
      });
      setPageSuccess(response.message);
    } catch (err: any) {
      const apiErr = err as ApiError;
      setPageError(apiErr.detail ? String(apiErr.detail) : 'Failed to start static Grok parsing.');
    } finally {
      setLoadingRun(false);
    }
  };

  const fetchCurrentTaskStatus = useCallback(async () => {
    if (!taskId) return;
    try {
      const statusData = await staticGrokService.getStaticGrokTaskStatus(taskId);
      setTaskStatusObj(statusData);

      if (statusData.completed || statusData.error) {
        if (statusData.error) setPageError(`Task Error: ${statusData.error}`);
        else setPageSuccess(`Task ${statusData.status}: ${statusData.progress_detail || 'Completed.'}`);
      }
    } catch (err) {
      const apiErr = err as ApiError;
      setPageError(apiErr.detail ? String(apiErr.detail) : 'Failed to fetch task status.');
      setTaskStatusObj(prev => prev ? {...prev, error: "Status fetch failed", completed: true} : {task_id: taskId, status: "Error", error: "Status fetch failed", completed:true, result_summary: null, last_updated: new Date().toISOString(), progress_detail: null});
    }
  }, [taskId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | undefined;
    if (isTaskRunning && taskId) {
      fetchCurrentTaskStatus();
      intervalId = setInterval(fetchCurrentTaskStatus, 5000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isTaskRunning, taskId, fetchCurrentTaskStatus]);

  const handleListStatuses = async () => {
    setLoadingStatusList(true); setPageError(null);
    try {
      const response = await staticGrokService.listStaticGrokStatuses(filterStatusGroup.trim() || undefined);
      setStatusList(response.statuses);
    } catch (err: any) {
      const apiErr = err as ApiError;
      setPageError(apiErr.detail ? String(apiErr.detail) : 'Failed to list parse statuses.');
    } finally {
      setLoadingStatusList(false);
    }
  };

  // handleSavePatternsToServerDefault removed
  // handlePatternsTextChange removed

  const handleDeleteData = async () => {
    if (!deleteAllGroupsData && !deleteGroupName.trim()) {
        setPageError("Please select a group or 'All Groups' for deletion.");
        return;
    }
    if (!window.confirm(`Are you sure you want to delete parsed data for ${deleteAllGroupsData ? 'ALL groups' : `group '${deleteGroupName}'`}? This cannot be undone.`)) {
        return;
    }
    setLoadingDelete(true); setPageError(null); setPageSuccess(null);
    try {
        const params: staticGrokService.StaticGrokDeleteRequest = {
            all_groups: deleteAllGroupsData,
            group_name: deleteAllGroupsData ? null : deleteGroupName.trim() || null,
        };
        const response = await staticGrokService.deleteStaticGrokParsedData(params);
        setPageSuccess(response.message);
        handleListStatuses();
    } catch (err: any) {
        const apiErr = err as ApiError;
        setPageError(apiErr.detail ? String(apiErr.detail) : 'Failed to delete parsed data.');
    } finally {
        setLoadingDelete(false);
    }
  };

  const handleConfirmServerPath = () => {
    if (grokPatternsFilePathOnServer.trim()) {
      if (!grokPatternsFilePathOnServer.startsWith('/') && !/^[a-zA-Z]:\\/.test(grokPatternsFilePathOnServer)) {
        setPageError("Server path should be absolute (e.g., /path/to/file or C:\\path\\to\\file).");
        setServerPathConfirmed(false);
        return;
      }
      if (!grokPatternsFilePathOnServer.toLowerCase().endsWith('.yaml') && !grokPatternsFilePathOnServer.toLowerCase().endsWith('.yml')) {
        setPageError("Server path should point to a YAML file (ends with .yaml or .yml).");
        setServerPathConfirmed(false);
        return;
      }
      setPageError(null);
      setServerPathConfirmed(true);
      setPageSuccess(`Server path '${grokPatternsFilePathOnServer}' set for run.`);
    } else {
      setPageError("Server path cannot be empty for confirmation.");
      setServerPathConfirmed(false);
    }
  };


  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Typography variant="h4" gutterBottom component="h1">
        Static Grok Parser Management
      </Typography>

      {pageError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setPageError(null)}>{pageError}</Alert>}
      {pageSuccess && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setPageSuccess(null)}>{pageSuccess}</Alert>}

      <Accordion sx={{ mb: 2 }} defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h5">Grok Patterns Source</Typography>
        </AccordionSummary>
        <AccordionDetails>
            {/* Removed Switch for useServerPathForPatterns and TextareaAutosize */}
            <Typography variant="subtitle1" sx={{mb:1}}>
                Provide the absolute path to your Grok patterns YAML file on the server.
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                <TextField
                    label="Grok Patterns YAML File Path on Server (Absolute)"
                    value={grokPatternsFilePathOnServer}
                    onChange={(e) => {
                        setGrokPatternsFilePathOnServer(e.target.value);
                        if (serverPathConfirmed) setServerPathConfirmed(false);
                    }}
                    fullWidth
                    helperText="e.g., /opt/logllm/custom_grok.yaml. This path will be used for the 'Run Parser' operation."
                    variant="outlined"
                    sx={{ flexGrow: 1 }}
                    disabled={loadingRun || isTaskRunning}
                />
                <Button
                    variant="outlined"
                    onClick={handleConfirmServerPath}
                    disabled={!grokPatternsFilePathOnServer.trim() || loadingRun || isTaskRunning }
                    startIcon={<CheckCircleOutlineIcon />}
                    sx={{ height: '56px', whiteSpace: 'nowrap' }}
                    color={serverPathConfirmed ? "success" : "primary"}
                >
                    {serverPathConfirmed ? "Path Confirmed" : "Confirm Path"}
                </Button>
            </Box>
            {/* Removed buttons for Save Editor, Reload Editor, Download Editor */}
        </AccordionDetails>
      </Accordion>

      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>Run Static Grok Parser</Typography>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={runAllGroups ? 12 : 5}>
            <FormControlLabel
              control={<Switch checked={runAllGroups} onChange={(e) => {setRunAllGroups(e.target.checked); if(e.target.checked) setRunGroupName('');}} />}
              label="Parse All Groups"
            />
          </Grid>
          {!runAllGroups && (
            <Grid item xs={12} sm={7}>
              <TextField
                select
                label="Select Group to Run"
                value={runGroupName}
                onChange={(e) => setRunGroupName(e.target.value)}
                fullWidth
                SelectProps={{ native: true }}
                disabled={runAllGroups}
                variant="outlined"
                InputLabelProps={{ shrink: true }}
              >
                <option value="">-- Select Specific Group --</option>
                {allDbGroups.map(g => <option key={`run-${g.group_name}`} value={g.group_name}>{g.group_name}</option>)}
              </TextField>
            </Grid>
          )}
          <Grid item xs={12}>
            <FormControlLabel
              control={<Switch checked={clearPrevious} onChange={(e) => setClearPrevious(e.target.checked)} />}
              label="Clear previous parsed data & status for selected group(s) before this run"
            />
             <Tooltip title="If checked, existing parsed_log_*, unparsed_log_* indices and static_grok_parse_status entries for the selected group(s) will be deleted before this run.">
                <IconButton size="small" sx={{verticalAlign: 'middle'}}><InfoOutlinedIcon fontSize="small" /></IconButton>
            </Tooltip>
          </Grid>
          <Grid item xs={12}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleRunParser}
              disabled={
                loadingRun ||
                isTaskRunning ||
                (!runAllGroups && !runGroupName.trim()) ||
                (!grokPatternsFilePathOnServer.trim() || !serverPathConfirmed) // Path must be set and confirmed
              }
            >
              {loadingRun || isTaskRunning ? <CircularProgress size={24} color="inherit" /> : <PlayArrowIcon/>}
              {isTaskRunning ? 'Parsing in Progress...' : 'Start Parsing Run'}
            </Button>
            {(!grokPatternsFilePathOnServer.trim() || !serverPathConfirmed) &&
                <Typography variant="caption" color="error" sx={{ml:1, display:'inline-block', verticalAlign: 'middle'}}>
                    {!grokPatternsFilePathOnServer.trim() ? "Server path is required." : "Server path not confirmed."}
                </Typography>
            }
          </Grid>
        </Grid>
      </Paper>

      {taskId && (
        <Paper elevation={2} sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6">Current Task Progress (ID: <Chip label={taskId.substring(0,8)} size="small" color="secondary"/>)</Typography>
          <Typography>Status: <Chip label={taskStatus || 'N/A'} size="small" color={taskStatus === 'Completed' ? 'success' : taskStatus === 'Error' ? 'error' : 'info'} /> </Typography>
          <Typography variant="body2">Details: {taskProgressDetail || 'N/A'}</Typography>
          {taskError && <Alert severity="error" sx={{ mt: 1 }}>Task Error: {taskError}</Alert>}
          {isTaskRunning && <CircularProgress size={20} sx={{ml:1, verticalAlign: 'middle'}}/>}
          {taskResultSummary && taskStatus === 'Completed' && !taskError && (
             <Box sx={{mt: 2}}>
                <Typography variant="subtitle1" sx={{fontWeight: 'bold'}}>Task Execution Summary:</Typography>
                <Typography variant="caption" display="block">Orchestrator Status: {taskResultSummary.orchestrator_status || "N/A"}</Typography>
                {taskResultSummary.orchestrator_errors && taskResultSummary.orchestrator_errors.length > 0 && (
                    <Typography variant="caption" color="error" display="block">Orchestrator Errors: {taskResultSummary.orchestrator_errors.join('; ')}</Typography>
                )}
                {Object.entries(taskResultSummary.groups_summary || {}).map(([grp, data]: [string, any]) => (
                    <Box key={grp} sx={{pl:1, borderLeft: '2px solid', borderColor: 'divider', my:1}}>
                        <Typography variant="caption" display="block" sx={{fontWeight:'medium'}}>
                            Group: {grp} - Status: {data.status} ({data.files_processed_count} files info)
                        </Typography>
                        {data.errors?.length > 0 && (
                             <Typography variant="caption" color="error" display="block" sx={{pl:1}}>- Errors: {data.errors.join('; ')}</Typography>
                        )}
                    </Box>
                ))}
             </Box>
          )}
        </Paper>
      )}

      <Accordion sx={{ mb: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h5">View Parsing Statuses</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
            <Grid item xs={12} sm={8}>
              <TextField
                select
                label="Filter by Group"
                value={filterStatusGroup}
                onChange={(e) => setFilterStatusGroup(e.target.value)}
                fullWidth
                size="small"
                SelectProps={{ native: true }}
                variant="outlined"
                InputLabelProps={{ shrink: true }}
              >
                <option value="">All Groups</option>
                {allDbGroups.map(g => <option key={`filter-status-${g.group_name}`} value={g.group_name}>{g.group_name}</option>)}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Button variant="outlined" onClick={handleListStatuses} disabled={loadingStatusList} startIcon={<RefreshIcon />}>
                {loadingStatusList ? <CircularProgress size={24} /> : 'List Statuses'}
              </Button>
            </Grid>
          </Grid>
          {loadingStatusList ? <CircularProgress /> : statusList.length > 0 ? (
            <TableContainer component={Paper} elevation={1}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Group</TableCell>
                    <TableCell>File Path</TableCell>
                    <TableCell align="right">Grok Line</TableCell>
                    <TableCell align="right">Collector Line</TableCell>
                    <TableCell>Last Status</TableCell>
                    <TableCell>Last Parsed</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {statusList.map(s => (
                    <TableRow hover key={s.log_file_id}>
                      <TableCell><Chip label={s.group_name || "N/A"} size="small" variant="outlined"/></TableCell>
                      <TableCell sx={{maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                        <Tooltip title={s.log_file_relative_path || "N/A"}><span>{s.log_file_relative_path || "N/A"}</span></Tooltip>
                      </TableCell>
                      <TableCell align="right">{s.last_line_number_parsed_by_grok}</TableCell>
                      <TableCell align="right">{s.last_total_lines_by_collector}</TableCell>
                      <TableCell>
                        <Chip
                            label={s.last_parse_status || "N/A"}
                            size="small"
                            color={s.last_parse_status?.includes("completed_new_data") ? "success" : s.last_parse_status?.includes("skipped") ? "info" : "default"}
                        />
                        </TableCell>
                      <TableCell>{s.last_parse_timestamp ? new Date(s.last_parse_timestamp).toLocaleString() : "N/A"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Typography sx={{py:2, textAlign:'center'}}>No status entries found for the current filter.</Typography>
          )}
        </AccordionDetails>
      </Accordion>

      <Paper elevation={2} sx={{
          p: 3, mt: 3,
          backgroundColor: lighten(theme.palette.error.main, 0.85)
        }}>
        <Typography variant="h5" gutterBottom color="error.dark">Danger Zone: Delete Parsed Data</Typography>
        <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={deleteAllGroupsData ? 12 : 5}>
                <FormControlLabel
                control={<Switch checked={deleteAllGroupsData} onChange={(e) => {setDeleteAllGroupsData(e.target.checked); if(e.target.checked) setDeleteGroupName('');}} />}
                label="Delete for ALL Groups"
                />
            </Grid>
            {!deleteAllGroupsData && (
                <Grid item xs={12} sm={7}>
                    <TextField
                        select
                        label="Select Group for Deletion"
                        value={deleteGroupName}
                        onChange={(e) => setDeleteGroupName(e.target.value)}
                        fullWidth
                        SelectProps={{ native: true }}
                        disabled={deleteAllGroupsData}
                        variant="outlined"
                        InputLabelProps={{ shrink: true }}
                    >
                        <option value="">-- Select Specific Group --</option>
                         {allDbGroups.map(g => <option key={`del-${g.group_name}`} value={g.group_name}>{g.group_name}</option>)}
                    </TextField>
                </Grid>
            )}
            <Grid item xs={12}>
                <Button
                    variant="contained"
                    sx={{ backgroundColor: theme.palette.error.main, '&:hover': {backgroundColor: theme.palette.error.dark}}}
                    onClick={handleDeleteData}
                    disabled={loadingDelete || (!deleteAllGroupsData && !deleteGroupName.trim())}
                    startIcon={<DeleteForeverIcon />}
                >
                    {loadingDelete ? <CircularProgress size={24} color="inherit" /> : 'Delete Parsed Data & Status'}
                </Button>
                <Typography variant="caption" display="block" color="error.dark" sx={{mt:1}}>
                    Warning: This will delete `parsed_log_*`, `unparsed_log_*` indices and `static_grok_parse_status` entries for the selected group(s). This action is irreversible.
                </Typography>
            </Grid>
        </Grid>
      </Paper>

    </Container>
  );
};

export default StaticGrokParserPage;

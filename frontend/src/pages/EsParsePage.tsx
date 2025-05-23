// frontend/src/pages/EsParsePage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Typography,
  Grid,
  TextField,
  Button,
  Card,
  CardContent,
  Paper,
  Box,
  CircularProgress,
  Alert,
  Switch,
  FormControlLabel,
  Divider,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Tooltip,
  IconButton
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RefreshIcon from '@mui/icons-material/Refresh';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

import {
  runEsParser,
  getEsParseTaskStatus,
  listEsParseResults,
  listEsParseGroups,
} from '../services/esParseService';
import type {
  EsParseRunRequest,
  EsParseResultItem,
  TaskStatusResponse,
  EsParseTaskGroupResult,
} from '../types/esParse';
import { AxiosError } from 'axios';

const EsParsePage: React.FC = () => {
  const initialRunConfig: EsParseRunRequest = {
    group_name: '',
    field_to_parse: 'content',
    copy_fields: [],
    batch_size: 1000,
    sample_size_generation: 20,
    validation_sample_size: 10,
    validation_threshold: 0.5,
    max_retries: 2,
    threads: 1,
    pattern: '',
    keep_unparsed_index: false,
  };

  const [runConfig, setRunConfig] = useState<EsParseRunRequest>(initialRunConfig);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [taskProgressDetail, setTaskProgressDetail] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [isTaskRunning, setIsTaskRunning] = useState<boolean>(false);
  const [taskCompletionSummary, setTaskCompletionSummary] = useState<Record<string, EsParseTaskGroupResult> | null>(null);

  const [results, setResults] = useState<EsParseResultItem[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [filterGroupForHistory, setFilterGroupForHistory] = useState<string>('');
  const [showAllHistory, setShowAllHistory] = useState<boolean>(false);

  const [isLoadingRun, setIsLoadingRun] = useState<boolean>(false);
  const [isLoadingResults, setIsLoadingResults] = useState<boolean>(false);
  const [isLoadingGroups, setIsLoadingGroups] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const handleRunConfigChange = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = event.target;
    if (type === 'checkbox') {
      const { checked } = event.target as HTMLInputElement;
      setRunConfig(prev => ({ ...prev, [name]: checked }));
    } else if (type === 'number') {
      setRunConfig(prev => ({ ...prev, [name]: value === '' ? '' : Number(value) }));
    } else {
      setRunConfig(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleCopyFieldsChange = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { value } = event.target;
    setRunConfig(prev => ({
      ...prev,
      copy_fields: value.split(',').map(field => field.trim()).filter(field => field),
    }));
  };

  const fetchTaskStatus = useCallback(async () => {
    if (!taskId) return;
    try {
      const statusData = await getEsParseTaskStatus(taskId);
      setTaskStatus(statusData.status);
      setTaskProgressDetail(statusData.progress_detail);
      setTaskError(statusData.error);

      if (statusData.completed || statusData.error) {
        setIsTaskRunning(false);
        if (statusData.result_summary) {
            setTaskCompletionSummary(statusData.result_summary);
        }
      }
    } catch (err) {
      console.error('Failed to fetch task status:', err);
      setTaskError('Failed to fetch task status.');
      setIsTaskRunning(false);
    }
  }, [taskId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | undefined;
    if (isTaskRunning && taskId) {
      fetchTaskStatus();
      intervalId = setInterval(fetchTaskStatus, 5000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isTaskRunning, taskId, fetchTaskStatus]);

  const handleStartParsing = async () => {
    setPageError(null);
    setTaskId(null);
    setTaskStatus(null);
    setTaskProgressDetail(null);
    setTaskError(null);
    setTaskCompletionSummary(null);
    setIsLoadingRun(true);
    setIsTaskRunning(true);

    const payload: EsParseRunRequest = {
        ...runConfig,
        group_name: runConfig.group_name?.trim() === '' ? null : runConfig.group_name,
        pattern: runConfig.pattern?.trim() === '' ? null : runConfig.pattern,
        copy_fields: runConfig.copy_fields && runConfig.copy_fields.length > 0 ? runConfig.copy_fields : null,
        batch_size: Number(runConfig.batch_size),
        sample_size_generation: Number(runConfig.sample_size_generation),
        validation_sample_size: Number(runConfig.validation_sample_size),
        validation_threshold: Number(runConfig.validation_threshold),
        max_retries: Number(runConfig.max_retries),
        threads: Number(runConfig.threads),
    };

    try {
      const response = await runEsParser(payload);
      const messageTaskIdMatch = response.message.match(/Task ID: (\S+)/);
      const extractedTaskId = messageTaskIdMatch ? messageTaskIdMatch[1] : null;

      setTaskId(extractedTaskId);
      setTaskStatus('Pending');
      setTaskProgressDetail('Task initiated by API.');
      if (!extractedTaskId) {
        setTaskError("API response did not include a Task ID in the expected format.");
        setIsTaskRunning(false);
      }
    } catch (err: any) {
      const error = err as AxiosError<{ detail?: string }>;
      setPageError(error.response?.data?.detail || 'Failed to start ES parsing process.');
      setTaskError(error.response?.data?.detail || 'Failed to start ES parsing process.');
      setIsTaskRunning(false);
    } finally {
      setIsLoadingRun(false);
    }
  };

  const handleListResults = async () => {
    setPageError(null);
    setIsLoadingResults(true);
    try {
      const response = await listEsParseResults(
        filterGroupForHistory.trim() === '' ? undefined : filterGroupForHistory,
        showAllHistory
      );
      setResults(response.results);
    } catch (err: any) {
      const error = err as AxiosError<{ detail?: string }>;
      setPageError(error.response?.data?.detail || 'Failed to list ES parse results.');
    } finally {
      setIsLoadingResults(false);
    }
  };

  const handleListGroups = async () => {
    setPageError(null);
    setIsLoadingGroups(true);
    try {
      const response = await listEsParseGroups();
      setGroups(response.groups);
    } catch (err: any) {
      const error = err as AxiosError<{ detail?: string }>;
      setPageError(error.response?.data?.detail || 'Failed to list groups with parsing history.');
    } finally {
      setIsLoadingGroups(false);
    }
  };

  const transformTaskSummaryToResultItem = (groupName: string, groupData: EsParseTaskGroupResult): EsParseResultItem => {
    const processed = groupData.final_parsing_results_summary?.processed ?? 0;
    const successful = groupData.final_parsing_results_summary?.successful ?? 0;
    let successPercentage: number | null = null;
    if (processed > 0) {
        successPercentage = parseFloat(((successful / processed) * 100).toFixed(2));
    }

    return {
        group_name: groupName,
        parsing_status: groupData.final_parsing_status,
        grok_pattern_used: groupData.current_grok_pattern || 'N/A',
        timestamp: new Date().toISOString(), // Represents task completion time
        processed_count: processed,
        successful_count: successful,
        failed_count: groupData.final_parsing_results_summary?.failed ?? 0,
        parse_error_count: groupData.final_parsing_results_summary?.parse_errors ?? 0,
        index_error_count: groupData.final_parsing_results_summary?.index_errors ?? 0,
        agent_error_count: groupData.error_messages?.length ?? 0,
        target_index: `parsed_log_${groupName.toLowerCase().replace(/[\s/.]/g, '_')}`,
        unparsed_index: `unparsed_log_${groupName.toLowerCase().replace(/[\s/.]/g, '_')}`,
        success_percentage: successPercentage,
        error_messages_summary: groupData.error_messages?.slice(0,3) ?? [],
    };
  };

  const renderResultItemCard = (item: EsParseResultItem, index: number | string) => (
    <Card key={`${item.group_name}-${item.timestamp}-${index}`} sx={{ mb: 2, width: '100%' }}>
      <CardContent>
        <Typography variant="h6" component="div">
          Group: {item.group_name}
          <Chip
            label={item.parsing_status}
            size="small"
            color={
                item.parsing_status.includes('success_fallback') ? 'warning' :
                item.parsing_status.includes('success_with_errors') ? 'info' :
                item.parsing_status.includes('success') ? 'success' :
                item.parsing_status.includes('failed') ? 'error' : 'default'
            }
            sx={{ ml: 2 }}
          />
        </Typography>
        <Typography sx={{ mb: 1.5 }} color="text.secondary">
          Recorded: {new Date(item.timestamp).toLocaleString()}
        </Typography>
        <Divider sx={{my:1}} />
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '100px', overflowY: 'auto', mb:1, p:1, border:'1px solid #eee', borderRadius:'4px', fontFamily: 'monospace' }}>
          <strong>Grok Pattern Used:</strong> {item.grok_pattern_used || 'N/A'}
        </Typography>
        <Grid container spacing={1}>
            <Grid item xs={12} sm={6} md={3}><Typography variant="body2"><strong>Processed:</strong> {item.processed_count}</Typography></Grid>
            <Grid item xs={12} sm={6} md={3}><Typography variant="body2"><strong>Successful:</strong> {item.successful_count}</Typography></Grid>
            <Grid item xs={12} sm={6} md={3}><Typography variant="body2" color={item.failed_count > 0 ? "error" : "inherit"}><strong>Failed/Fallback:</strong> {item.failed_count}</Typography></Grid>
            <Grid item xs={12} sm={6} md={3}>
                <Typography variant="body2">
                    <strong>Success %:</strong> {item.success_percentage !== null && item.success_percentage !== undefined ? `${item.success_percentage}%` : 'N/A'}
                </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}><Typography variant="body2" color={item.parse_error_count > 0 ? "error" : "inherit"}><strong>Parse Errors:</strong> {item.parse_error_count}</Typography></Grid>
            <Grid item xs={12} sm={6} md={3}><Typography variant="body2" color={item.index_error_count > 0 ? "error" : "inherit"}><strong>Index Errors:</strong> {item.index_error_count}</Typography></Grid>
            <Grid item xs={12} sm={6} md={3}><Typography variant="body2" color={item.agent_error_count > 0 ? "error" : "inherit"}><strong>Agent Errors:</strong> {item.agent_error_count}</Typography></Grid>
        </Grid>
        <Divider sx={{my:1}} />
        <Typography variant="caption" display="block">Target Index: {item.target_index}</Typography>
        <Typography variant="caption" display="block">Unparsed Index: {item.unparsed_index}</Typography>
        {item.error_messages_summary && item.error_messages_summary.length > 0 && (
            <Box mt={1}>
                <Typography variant="body2" color="error" sx={{fontWeight: 'bold'}}>Key Agent Error Messages:</Typography>
                {item.error_messages_summary.map((err, i) => <Typography key={i} variant="caption" color="error" display="block" sx={{fontFamily: 'monospace'}}>- {err}</Typography>)}
            </Box>
        )}
      </CardContent>
    </Card>
  );

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Typography variant="h4" gutterBottom component="h1">
        Elasticsearch Log Parser (Grok)
      </Typography>

      {pageError && <Alert severity="error" sx={{ mb: 2 }}>{pageError}</Alert>}

      <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>Configuration & Run</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}><TextField label="Group Name (optional)" name="group_name" value={runConfig.group_name} onChange={handleRunConfigChange} fullWidth helperText="Leave blank to parse all groups" /></Grid>
          <Grid item xs={12} sm={6}><TextField label="Field to Parse" name="field_to_parse" value={runConfig.field_to_parse} onChange={handleRunConfigChange} fullWidth required /></Grid>
          <Grid item xs={12}><TextField label="Copy Fields (comma-separated)" name="copy_fields_display" value={runConfig.copy_fields?.join(', ') || ''} onChange={handleCopyFieldsChange} fullWidth helperText="e.g., host.name, service.name" /></Grid>
          <Grid item xs={12}><TextField label="Grok Pattern (optional, for single group only)" name="pattern" value={runConfig.pattern} onChange={handleRunConfigChange} fullWidth multiline minRows={2} maxRows={4} /></Grid>

          <Grid item xs={6} sm={3}><TextField label="Batch Size" name="batch_size" type="number" value={runConfig.batch_size} onChange={handleRunConfigChange} fullWidth InputProps={{ inputProps: { min: 1 } }} /></Grid>
          <Grid item xs={6} sm={3}>
            <TextField
                label="Threads (all groups)"
                name="threads"
                type="number"
                value={runConfig.threads}
                onChange={handleRunConfigChange}
                fullWidth
                InputProps={{ inputProps: { min: 1 } }}
                helperText={runConfig.group_name ? "Ignored for single group" : ""}
                disabled={!!runConfig.group_name}
            />
          </Grid>
          <Grid item xs={6} sm={3}><TextField label="Sample Size (Gen)" name="sample_size_generation" type="number" value={runConfig.sample_size_generation} onChange={handleRunConfigChange} fullWidth InputProps={{ inputProps: { min: 1 } }} /></Grid>
          <Grid item xs={6} sm={3}><TextField label="Sample Size (Val)" name="validation_sample_size" type="number" value={runConfig.validation_sample_size} onChange={handleRunConfigChange} fullWidth InputProps={{ inputProps: { min: 1 } }} /></Grid>

          <Grid item xs={6} sm={4}><TextField label="Validation Threshold" name="validation_threshold" type="number" value={runConfig.validation_threshold} onChange={handleRunConfigChange} fullWidth InputProps={{ inputProps: { min: 0, max: 1, step: 0.01 } }} /></Grid>
          <Grid item xs={6} sm={4}><TextField label="Max Retries (Gen)" name="max_retries" type="number" value={runConfig.max_retries} onChange={handleRunConfigChange} fullWidth InputProps={{ inputProps: { min: 0 } }} /></Grid>
          <Grid item xs={12} sm={4} sx={{display: 'flex', alignItems: 'center'}}>
            <FormControlLabel
              control={<Switch checked={runConfig.keep_unparsed_index} onChange={handleRunConfigChange} name="keep_unparsed_index" />}
              label="Keep Unparsed Index"
            />
             <Tooltip title="If checked, the existing index for unparsed logs (e.g., unparsed_log_yourgroup) will not be deleted before this run. New unparsed logs will be appended.">
                <IconButton size="small"><InfoOutlinedIcon fontSize="small" /></IconButton>
            </Tooltip>
          </Grid>
          <Grid item xs={12}>
            <Button variant="contained" color="primary" onClick={handleStartParsing} disabled={isLoadingRun || isTaskRunning}>
              {isLoadingRun || isTaskRunning ? <CircularProgress size={24} /> : 'Start Parsing'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {taskId && (
        <Paper elevation={2} sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6">Current Task (ID: {taskId})</Typography>
          <Typography>Status: <Chip label={taskStatus || 'N/A'} size="small" color={taskStatus === 'Completed' ? 'success' : taskStatus === 'Error' ? 'error' : 'info'} /> </Typography>
          <Typography>Details: {taskProgressDetail || 'N/A'}</Typography>
          {taskError && <Alert severity="error" sx={{ mt: 1 }}>Error: {taskError}</Alert>}
          {isTaskRunning && <CircularProgress size={20} sx={{ml:1, verticalAlign: 'middle'}}/>}

          {taskStatus === "Completed" && !taskError && taskCompletionSummary && (
            <Box mt={2}>
                <Typography variant="subtitle1" gutterBottom sx={{fontWeight: 'bold'}}>Task Execution Summary:</Typography>
                {Object.entries(taskCompletionSummary).map(([groupName, groupData]) =>
                    renderResultItemCard(transformTaskSummaryToResultItem(groupName, groupData), `task-${groupName}`)
                )}
            </Box>
          )}
        </Paper>
      )}

      <Accordion sx={{ mb: 3 }} TransitionProps={{ unmountOnExit: true }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h5">Historical Parsing Results</Typography>
        </AccordionSummary>
        <AccordionDetails>
            <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
              <Grid item xs={12} sm={5}>
                <TextField label="Filter by Group Name (optional)" value={filterGroupForHistory} onChange={(e) => setFilterGroupForHistory(e.target.value)} fullWidth size="small"/>
              </Grid>
              <Grid item xs={12} sm={3}>
                <FormControlLabel
                    control={<Switch checked={showAllHistory} onChange={(e) => setShowAllHistory(e.target.checked)} />}
                    label="Show All History"
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <Button variant="outlined" onClick={handleListResults} disabled={isLoadingResults} startIcon={<RefreshIcon />}>
                  {isLoadingResults ? <CircularProgress size={24} /> : 'List Results'}
                </Button>
              </Grid>
            </Grid>
            {isLoadingResults && <Box sx={{display: 'flex', justifyContent: 'center', my:2}}><CircularProgress /></Box>}
            {!isLoadingResults && results.length > 0 ? (
                results.map(renderResultItemCard)
            ) : (
                !isLoadingResults && <Typography sx={{py:2}}>No historical results to display. Use filters and click "List Results".</Typography>
            )}
        </AccordionDetails>
      </Accordion>

      <Accordion TransitionProps={{ unmountOnExit: true }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h5">Groups with Parsing History</Typography>
        </AccordionSummary>
        <AccordionDetails>
            <Button variant="outlined" onClick={handleListGroups} disabled={isLoadingGroups} sx={{ mb: 2 }} startIcon={<RefreshIcon />}>
              {isLoadingGroups ? <CircularProgress size={24} /> : 'List Groups'}
            </Button>
            {isLoadingGroups && <Box sx={{display: 'flex', justifyContent: 'center', my:2}}><CircularProgress /></Box>}
            {!isLoadingGroups && groups.length > 0 ? (
              <Box>
                {groups.map(group => <Chip key={group} label={group} sx={{ mr: 1, mb: 1 }} onClick={() => setFilterGroupForHistory(group)} />)}
              </Box>
            ) : (
              !isLoadingGroups && <Typography sx={{py:2}}>No groups found with parsing history.</Typography>
            )}
        </AccordionDetails>
      </Accordion>

    </Container>
  );
};

export default EsParsePage;

// frontend/src/pages/GroupInfoPage.tsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  Box,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import FolderIcon from '@mui/icons-material/Folder'; // For group icon
import DescriptionIcon from '@mui/icons-material/Description'; // For file count icon

import * as groupService from '../services/groupService';
import type { GroupInfoDetail } from '../types/group';
import type { ApiError } from '../types/api';

const GroupInfoPage: React.FC = () => {
  const [groups, setGroups] = useState<GroupInfoDetail[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGroupInfo = useCallback(async (showLoadingSpinner: boolean = true) => {
    if (showLoadingSpinner) setLoading(true);
    setError(null);
    try {
      const response = await groupService.listAllGroupsInfo();
      setGroups(response.groups);
    } catch (err) {
      const apiError = err as ApiError;
      let errorMessage = 'Failed to fetch group information.';
      if (typeof apiError.detail === 'string') {
        errorMessage = apiError.detail;
      } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0 && typeof apiError.detail[0] === 'object' && apiError.detail[0].msg) {
        errorMessage = apiError.detail[0].msg;
      } else if ((err as Error).message) {
        errorMessage = (err as Error).message;
      }
      setError(errorMessage);
      setGroups([]);
    } finally {
      if (showLoadingSpinner) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGroupInfo();
  }, [fetchGroupInfo]);

  return (
    <Paper sx={{ p: 3, maxWidth: 900, margin: 'auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" gutterBottom component="div">
          Collected Group Information
        </Typography>
        <Tooltip title="Refresh Group List">
          <IconButton onClick={() => fetchGroupInfo(true)} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>
      <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
        This page displays information about the log groups that have been identified and potentially processed by the collector.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 5 }}>
          <CircularProgress size={50} />
        </Box>
      ) : groups.length === 0 && !error ? (
        <Alert severity="info" sx={{ mt: 2 }}>
          No group information found. Please run the collection process first.
        </Alert>
      ) : (
        <TableContainer component={Paper} elevation={2}>
          <Table aria-label="group information table">
            <TableHead sx={{ backgroundColor: (theme) => theme.palette.action.hover }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <FolderIcon sx={{ mr: 1, color: 'primary.main' }} /> Group Name
                  </Box>
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                    <DescriptionIcon sx={{ mr: 1, color: 'secondary.main' }} /> File Count
                  </Box>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {groups.map((group) => (
                <TableRow
                  key={group.group_name}
                  sx={{ '&:last-child td, &:last-child th': { border: 0 }, '&:hover': { backgroundColor: (theme) => theme.palette.action.selected } }}
                >
                  <TableCell component="th" scope="row">
                    <Chip label={group.group_name} variant="outlined" color="primary" />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">{group.file_count}</Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
};

export default GroupInfoPage;

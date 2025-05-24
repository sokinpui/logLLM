// frontend/src/services/staticGrokParseService.ts
import apiClient from "./api"; // Assuming apiClient is refactored from ./api
import type { MessageResponse } from "../types/api"; // Common message response

// Define request/response types specific to static-grok-parser
// These should mirror Pydantic models in static_grok_parse_router.py

export interface StaticGrokRunRequest {
  group_name?: string | null;
  all_groups?: boolean;
  clear_previous_results?: boolean;
  grok_patterns_file_content?: string | null; // Content of the YAML file
  grok_patterns_file_path_on_server?: string | null; // ADDED: Path to patterns file on server
}

export interface StaticGrokTaskInfo {
  task_id: string;
  message: string;
}

export interface StaticGrokTaskStatus {
  task_id: string; // Though task_id is part of URL, good to have it in response too
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
  result_summary?: Record<string, any> | null; // Generic summary for now
}

export interface StaticGrokParseStatusItem {
  log_file_id: string;
  group_name?: string | null;
  log_file_relative_path?: string | null;
  last_line_number_parsed_by_grok: number; // Changed from last_line_parsed_by_grok
  last_total_lines_by_collector: number;
  last_parse_timestamp?: string | null;
  last_parse_status?: string | null;
}

export interface StaticGrokStatusListResponse {
  statuses: StaticGrokParseStatusItem[];
  total: number;
}

export interface StaticGrokDeleteRequest {
  group_name?: string | null;
  all_groups?: boolean;
}

export interface GrokPatternsFileResponse {
  filename: string;
  content: string;
  error?: string | null;
}

const API_PREFIX = "/static-grok-parser";

export const runStaticGrokParser = async (
  params: StaticGrokRunRequest,
): Promise<StaticGrokTaskInfo> => {
  return apiClient<StaticGrokTaskInfo>(`${API_PREFIX}/run`, {
    method: "POST",
    body: JSON.stringify(params),
  });
};

export const getStaticGrokTaskStatus = async (
  taskId: string,
): Promise<StaticGrokTaskStatus> => {
  return apiClient<StaticGrokTaskStatus>(`${API_PREFIX}/task-status/${taskId}`);
};

export const listStaticGrokStatuses = async (
  groupName?: string,
): Promise<StaticGrokStatusListResponse> => {
  let endpoint = `${API_PREFIX}/list-status`;
  if (groupName) {
    endpoint += `?group_name=${encodeURIComponent(groupName)}`;
  }
  return apiClient<StaticGrokStatusListResponse>(endpoint);
};

export const deleteStaticGrokParsedData = async (
  params: StaticGrokDeleteRequest,
): Promise<MessageResponse> => {
  return apiClient<MessageResponse>(`${API_PREFIX}/delete-parsed-data`, {
    method: "POST",
    body: JSON.stringify(params),
  });
};

export const getGrokPatternsFile =
  async (): Promise<GrokPatternsFileResponse> => {
    return apiClient<GrokPatternsFileResponse>(
      `${API_PREFIX}/config/grok-patterns`,
    );
  };

export const updateGrokPatternsFile = async (
  file: File,
): Promise<MessageResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  // For FormData, apiClient needs to handle it without stringifying and set Content-Type to multipart/form-data
  // The current apiClient might need adjustment for FormData
  // For now, let's assume apiClient can handle FormData or modify it:
  // Adjust apiClient or use fetch directly for FormData
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api"}${API_PREFIX}/config/grok-patterns`,
    {
      method: "POST",
      body: formData,
      // Headers will be set automatically by browser for FormData
    },
  );
  if (!response.ok) {
    const errorData = await response
      .json()
      .catch(() => ({ detail: "Failed to upload patterns file" }));
    throw new Error(
      errorData.detail || `HTTP error! status: ${response.status}`,
    );
  }
  return response.json();
};

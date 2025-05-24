// frontend/src/services/staticGrokParseService.ts
import apiClient from "./api";
import type { MessageResponse } from "../types/api";

export interface StaticGrokRunRequest {
  group_name?: string | null;
  all_groups?: boolean;
  clear_previous_results?: boolean;
  grok_patterns_file_content?: string | null; // Keep as optional for API flexibility, but UI won't send it
  grok_patterns_file_path_on_server: string; // Now mandatory from UI perspective for run
}

// ... rest of the file remains the same
export interface StaticGrokTaskInfo {
  task_id: string;
  message: string;
}

export interface StaticGrokTaskStatus {
  task_id: string;
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
  result_summary?: Record<string, any> | null;
}

export interface StaticGrokParseStatusItem {
  log_file_id: string;
  group_name?: string | null;
  log_file_relative_path?: string | null;
  last_line_number_parsed_by_grok: number;
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
  // This type is no longer used if endpoints are removed
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

// getGrokPatternsFile and updateGrokPatternsFile can be removed if their corresponding
// backend endpoints are removed. For now, I'll leave them, but they are unused by the modified UI.
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
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api"}${API_PREFIX}/config/grok-patterns`,
    {
      method: "POST",
      body: formData,
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

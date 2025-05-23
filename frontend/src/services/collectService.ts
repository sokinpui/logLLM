import apiClient from "./api";
import type { MessageResponse } from "../types/api";
import type {
  DirectoryAnalysisResponse,
  TaskStatusResponse,
} from "../types/collect";

const API_ENDPOINT = "/collect";

export interface ServerPathRequest {
  directory: string;
}

// --- Service for analyzing server path structure ---
export const analyzeServerPathStructure = async (
  params: ServerPathRequest,
): Promise<DirectoryAnalysisResponse> => {
  return apiClient<DirectoryAnalysisResponse>(
    `${API_ENDPOINT}/analyze-structure`,
    {
      method: "POST",
      body: JSON.stringify(params),
    },
  );
};

// --- Service to start collection from a server path ---
export const startCollectionFromServerPath = async (
  params: ServerPathRequest,
): Promise<MessageResponse & { task_id?: string }> => {
  return apiClient<MessageResponse & { task_id?: string }>(
    `${API_ENDPOINT}/from-server-path`,
    {
      method: "POST",
      body: JSON.stringify(params),
    },
  );
};

// --- Service to get task status ---
export const getCollectionTaskStatus = async (
  taskId: string,
): Promise<TaskStatusResponse> => {
  return apiClient<TaskStatusResponse>(`${API_ENDPOINT}/task-status/${taskId}`);
};

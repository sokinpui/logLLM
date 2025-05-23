// frontend/src/services/esParseService.ts
import apiClient from "./api";
import type {
  EsParseRunRequest,
  EsParseListResponse,
  EsParseGroupListResponse,
  TaskStatusResponse,
  MessageResponse,
} from "../types/esParse";

const API_PREFIX = "/es-parser";

export const runEsParser = async (
  config: EsParseRunRequest,
): Promise<MessageResponse> => {
  const response = await apiClient.post<MessageResponse>(
    `${API_PREFIX}/run`,
    config,
  );
  return response.data;
};

export const getEsParseTaskStatus = async (
  taskId: string,
): Promise<TaskStatusResponse> => {
  const response = await apiClient.get<TaskStatusResponse>(
    `${API_PREFIX}/task-status/${taskId}`,
  );
  return response.data;
};

export const listEsParseResults = async (
  group?: string,
  allHistory?: boolean,
): Promise<EsParseListResponse> => {
  const params: Record<string, any> = {};
  if (group) {
    params.group = group;
  }
  if (allHistory !== undefined) {
    params.all_history = allHistory;
  }
  const response = await apiClient.get<EsParseListResponse>(
    `${API_PREFIX}/list-results`,
    { params },
  );
  return response.data;
};

export const listEsParseGroups =
  async (): Promise<EsParseGroupListResponse> => {
    const response = await apiClient.get<EsParseGroupListResponse>(
      `${API_PREFIX}/list-groups`,
    );
    return response.data;
  };

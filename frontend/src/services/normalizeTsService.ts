// frontend/src/services/normalizeTsService.ts
import apiClient from "./api";
import type { MessageResponse } from "../types/api";
import type {
  NormalizeTsRunRequest,
  NormalizeTsTaskStatusResponse,
} from "../types/normalizeTs";

const API_ENDPOINT = "/normalize-ts";

export const runNormalizeTsTask = async (
  params: NormalizeTsRunRequest,
): Promise<MessageResponse> => {
  // The apiClient should handle stringifying the body
  return apiClient<MessageResponse>(`${API_ENDPOINT}/run`, {
    method: "POST",
    body: JSON.stringify(params),
  });
};

export const getNormalizeTsTaskStatus = async (
  taskId: string,
): Promise<NormalizeTsTaskStatusResponse> => {
  return apiClient<NormalizeTsTaskStatusResponse>(
    `${API_ENDPOINT}/task-status/${taskId}`,
  );
};

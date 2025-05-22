// --- Create file: frontend/src/services/containerService.ts ---
import apiClient from "./api";
import type {
  ContainerStatusResponse,
  MessageResponse,
  ContainerStopRequest,
} from "../types/api";

const API_ENDPOINT = "/container";

export const getContainerStatus =
  async (): Promise<ContainerStatusResponse> => {
    return apiClient<ContainerStatusResponse>(`${API_ENDPOINT}/status`);
  };

export const startContainers = async (): Promise<MessageResponse> => {
  return apiClient<MessageResponse>(`${API_ENDPOINT}/start`, {
    method: "POST",
  });
};

export const stopContainers = async (
  params: ContainerStopRequest,
): Promise<MessageResponse> => {
  return apiClient<MessageResponse>(`${API_ENDPOINT}/stop`, {
    method: "POST",
    body: JSON.stringify(params),
  });
};

export const restartContainers = async (): Promise<MessageResponse> => {
  return apiClient<MessageResponse>(`${API_ENDPOINT}/restart`, {
    method: "POST",
  });
};

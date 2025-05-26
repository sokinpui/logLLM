// frontend/src/services/analyzeErrorsService.ts
import apiClient from "./api";
import type {
  AnalyzeErrorsRunParams,
  AnalyzeErrorsTaskStatusResponse,
  TaskInitiationResponse,
  ListErrorSummariesResponse,
  ErrorSummaryListItem, // Not strictly needed here but good for context
} from "../types/analyzeErrors";

const API_ENDPOINT = "/analyze-errors";

export const runErrorSummaryAnalysis = async (
  params: AnalyzeErrorsRunParams,
): Promise<TaskInitiationResponse> => {
  return apiClient<TaskInitiationResponse>(`${API_ENDPOINT}/run-summary`, {
    method: "POST",
    body: JSON.stringify(params),
  });
};

export const getErrorAnalysisTaskStatus = async (
  taskId: string,
): Promise<AnalyzeErrorsTaskStatusResponse> => {
  return apiClient<AnalyzeErrorsTaskStatusResponse>(
    `${API_ENDPOINT}/task-status/${taskId}`,
  );
};

export const listGeneratedErrorSummaries = async (
  params: {
    group_name?: string | null;
    start_time?: string | null; // ISO String
    end_time?: string | null; // ISO String
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_order?: "asc" | "desc";
  } = {},
): Promise<ListErrorSummariesResponse> => {
  const queryParams = new URLSearchParams();
  if (params.group_name) queryParams.append("group_name", params.group_name);
  if (params.start_time) queryParams.append("start_time", params.start_time);
  if (params.end_time) queryParams.append("end_time", params.end_time);
  if (params.limit !== undefined)
    queryParams.append("limit", String(params.limit));
  if (params.offset !== undefined)
    queryParams.append("offset", String(params.offset));
  if (params.sort_by) queryParams.append("sort_by", params.sort_by);
  if (params.sort_order) query_params.append("sort_order", params.sort_order);

  const endpoint = `${API_ENDPOINT}/list-summaries${queryParams.toString() ? `?${queryParams.toString()}` : ""}`;
  return apiClient<ListErrorSummariesResponse>(endpoint);
};

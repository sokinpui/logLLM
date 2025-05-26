// frontend/src/types/analyzeErrors.ts

// Mirrors Pydantic AnalyzeErrorsRunParams
export interface AnalyzeErrorsRunParams {
  group_name: string;
  start_time_iso: string;
  end_time_iso: string;
  error_log_levels?: string[]; // Will be sent as a list of strings
  max_logs_to_process?: number;
  embedding_model_name?: string;
  llm_model_for_summary?: string;
  dbscan_eps?: number;
  dbscan_min_samples?: number;
  max_samples_per_cluster?: number;
  max_samples_unclustered?: number;
  target_summary_index?: string;
}

// Mirrors Pydantic LogClusterSummaryOutput
export interface LogClusterSummaryOutput {
  summary: string;
  potential_cause?: string | null;
  keywords: string[];
  representative_log_line?: string | null;
}

// Part of the result_summary in AnalyzeErrorsTaskStatusResponse
export interface ProcessedClusterDetail {
  cluster_id_internal: number | string; // -1 for unclustered, number for DBSCAN
  cluster_label: string; // e.g., "unclustered", "cluster_0"
  total_logs_in_cluster: number;
  unique_messages_in_cluster?: number;
  cluster_time_range_start?: string | null;
  cluster_time_range_end?: string | null;
  sampled_log_messages_used?: string[];
  summary_generated: boolean;
  summary_document_id_es?: string | null;
  summary_output?: LogClusterSummaryOutput | null; // This will hold the LLM's structured summary
}

// Structure for the 'result_summary' field within AnalyzeErrorsTaskStatusResponse
export interface AnalysisResultSummary {
  agent_status?: string | null;
  processed_cluster_details: ProcessedClusterDetail[];
  final_summary_ids_count?: number;
  errors_during_run?: string[];
  raw_logs_fetched_count?: number;
}

// Mirrors Pydantic AnalyzeErrorsTaskStatusResponse
export interface AnalyzeErrorsTaskStatusResponse {
  task_id: string;
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
  result_summary?: AnalysisResultSummary | null; // Use the more detailed structure here
  params_used?: AnalyzeErrorsRunParams; // To show what params were used for this task
}

// Mirrors Pydantic TaskInitiationResponse
export interface TaskInitiationResponse {
  task_id: string;
  message: string;
}

// Mirrors Pydantic ErrorSummaryListItem
export interface ErrorSummaryListItem {
  summary_id: string; // from _id
  group_name: string;
  cluster_id: string;
  summary_text: string;
  potential_cause_text?: string | null;
  keywords: string[];
  generation_timestamp: string;
  analysis_start_time: string;
  analysis_end_time: string;
  llm_model_used: string;
  sample_log_count: number;
  total_logs_in_cluster: number;
}

// Mirrors Pydantic ListErrorSummariesResponse
export interface ListErrorSummariesResponse {
  summaries: ErrorSummaryListItem[];
  total: number;
  offset: number;
  limit: number;
}

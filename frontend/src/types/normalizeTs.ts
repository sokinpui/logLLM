// frontend/src/types/normalizeTs.ts

export interface NormalizeTsRunRequest {
  action: "normalize" | "remove_field";
  group_name?: string | null;
  all_groups: boolean;
  limit_per_group?: number | null;
  batch_size: number;
  confirm_delete?: boolean;
}

// Corresponds to TimestampNormalizerGroupState from Python
export interface NormalizeTsTaskGroupResult {
  group_name: string;
  parsed_log_index: string;
  status_this_run: string; // e.g., "pending", "normalizing", "completed"
  error_message_this_run?: string | null;
  documents_scanned_this_run: number;
  documents_updated_this_run: number;
  timestamp_normalization_errors_this_run: number; // Specific to 'normalize'
}

export interface NormalizeTsTaskStatusResponse {
  task_id: string;
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
  result_summary?: Record<string, NormalizeTsTaskGroupResult> | null;
}

export interface MessageResponse {
  message: string;
}

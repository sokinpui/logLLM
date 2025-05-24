// frontend/src/types/esParse.ts

export interface EsParseRunRequest {
  group_name?: string | null;
  field_to_parse: string;
  copy_fields?: string[] | null;
  batch_size: number;
  sample_size_generation: number;
  validation_sample_size: number;
  validation_threshold: number;
  max_retries: number;
  threads: number;
  pattern?: string | null;
  keep_unparsed_index: boolean;
}

export interface EsParseResultItem {
  group_name: string;
  parsing_status: string;
  grok_pattern_used?: string | null;
  timestamp: string;
  processed_count: number;
  successful_count: number;
  failed_count: number;
  parse_error_count: number;
  index_error_count: number;
  agent_error_count: number;
  target_index: string;
  unparsed_index: string;
  success_percentage?: number | null;
  error_messages_summary?: string[] | null;
}

export interface EsParseListResponse {
  results: EsParseResultItem[];
  total: number;
}

export interface EsParseGroupListResponse {
  groups: string[];
  total: number;
}

export interface EsParseTaskGroupResult {
  final_parsing_status: string;
  current_grok_pattern?: string | null;
  final_parsing_results_summary?: {
    processed: number;
    successful: number;
    failed: number;
    parse_errors: number;
    index_errors: number;
  } | null;
  error_messages?: string[];
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
  result_summary?: Record<string, EsParseTaskGroupResult> | null;
}

export interface MessageResponse {
  message: string;
}

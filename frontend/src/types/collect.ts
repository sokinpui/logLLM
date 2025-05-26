// --- Update: frontend/src/types/collect.ts ---
export interface GroupInfo {
  name: string;
  file_count: number; // Ensure snake_case from Pydantic model is handled or alias in Pydantic
}

export interface DirectoryAnalysisResponse {
  path_exists: boolean;
  root_files_present: boolean;
  identified_groups: GroupInfo[];
  error_message?: string | null;
  scanned_path: string;
}

// --- New types for collection summary ---
export interface GroupCollectionSummary {
  group_name: string;
  files_processed_in_group: number; // Renamed for clarity
  new_lines_ingested_in_group: number; // Renamed for clarity
  // You could add more, e.g., total_files_in_group_after_collection
}

export interface CollectionSummary {
  total_groups_processed: number;
  total_files_processed_overall: number;
  total_new_lines_ingested_overall: number;
  details_per_group: GroupCollectionSummary[];
}
// --- End of new types ---

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
  collection_summary?: CollectionSummary | null; // Added field for summary
}

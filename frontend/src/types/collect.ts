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

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  progress_detail?: string | null;
  completed: boolean;
  error?: string | null;
  last_updated?: string | null;
}

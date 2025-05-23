// frontend/src/types/group.ts
export interface GroupInfoDetail {
  group_name: string;
  file_count: number;
  // sample_files?: string[]; // Future enhancement
}

export interface GroupInfoListResponse {
  groups: GroupInfoDetail[];
}

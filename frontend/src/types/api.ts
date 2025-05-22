export interface MessageResponse {
  message: string;
}

export interface ContainerDetailItem {
  // Renamed from ContainerStatusItem
  name: string;
  status: string;
  container_id?: string | null; // Changed from id to container_id to match Pydantic alias
  short_id?: string | null;
  ports?: string[] | null;
  mounts?: string[] | null;
}

export interface VolumeDetailItem {
  name: string;
  status: string; // e.g., "found", "not_found", "error"
  driver?: string | null;
  mountpoint?: string | null;
  scope?: string | null;
}

export interface ContainerStatusResponse {
  statuses: ContainerDetailItem[];
  volume_info?: VolumeDetailItem | null; // Added
}

export interface ContainerStopRequest {
  remove?: boolean;
}

// Generic API error structure (FastAPI often returns detail)
export interface ApiError {
  detail: string | { msg: string; type: string }[]; // Accommodate FastAPI's validation error format too
}

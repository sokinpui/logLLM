export interface MessageResponse {
  message: string;
}

export interface ContainerDetailItem {
  name: string;
  status: string;
  container_id?: string | null;
  short_id?: string | null;
  ports?: string[] | null;
  mounts?: string[] | null;
  service_status?: string | null; // Status of the service itself (e.g., healthy, green, yellow, red, available)
  service_url?: string | null; // URL to access the service, e.g., Kibana dashboard
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
  volume_info?: VolumeDetailItem | null;
}

export interface ContainerStopRequest {
  remove?: boolean;
}

// Generic API error structure (FastAPI often returns detail)
export interface ApiError {
  detail: string | { msg: string; type: string }[]; // Accommodate FastAPI's validation error format too
}

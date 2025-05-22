// --- Create file: frontend/src/types/api.ts ---
export interface MessageResponse {
  message: string;
}

export interface ContainerStatusItem {
  name: string;
  status: string;
}

export interface ContainerStatusResponse {
  statuses: ContainerStatusItem[];
}

export interface ContainerStopRequest {
  remove?: boolean;
}

// Generic API error structure (FastAPI often returns detail)
export interface ApiError {
  detail: string | { msg: string; type: string }[]; // Accommodate FastAPI's validation error format too
}

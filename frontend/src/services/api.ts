// Example for a base API client setup (e.g., using Axios)
// You can expand this later

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Placeholder function, replace with actual client like Axios
async function apiClient<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorData = await response
      .json()
      .catch(() => ({ message: "Request failed" }));
    throw new Error(
      errorData.message || `HTTP error! status: ${response.status}`,
    );
  }
  return response.json();
}

export default apiClient;

// Example service structure (create separate files like containerService.ts, etc.)
/*
// In services/containerService.ts
import apiClient from './api';

interface ContainerStatus {
  name: string;
  status: string;
}

export const getContainerStatus = async (): Promise<ContainerStatus[]> => {
  // TODO: Implement actual API call
  // return apiClient<{ es_status: string, kbn_status: string }>('/container/status');
  console.log('Fetching container status (mock)');
  return Promise.resolve([
    { name: 'movelook_elastic_search', status: 'running (mock)' },
    { name: 'movelook_kibana', status: 'stopped (mock)' },
  ]);
};

export const startContainers = async (): Promise<any> => {
  console.log('Starting containers (mock)');
  return Promise.resolve({ message: 'Containers starting (mock)' });
  // return apiClient('/container/start', { method: 'POST' });
}
// ... other container actions
*/

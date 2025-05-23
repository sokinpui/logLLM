// frontend/src/services/groupService.ts
import apiClient from "./api";
import type { GroupInfoListResponse } from "../types/group";

const API_ENDPOINT = "/groups";

export const listAllGroupsInfo = async (): Promise<GroupInfoListResponse> => {
  return apiClient<GroupInfoListResponse>(`${API_ENDPOINT}/`);
};

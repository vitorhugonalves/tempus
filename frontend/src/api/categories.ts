import apiClient from "./client";
import type { Category } from "../types";

export const categoriesApi = {
  list: (competitionId: number, onlyActive?: boolean) => {
    const params = onlyActive ? { only_active: true } : {};
    return apiClient
      .get<Category[]>(`/api/v1/competitions/${competitionId}/categories`, { params })
      .then((r) => r.data);
  },

  create: (
    competitionId: number,
    data: { name: string; category_type: string; max_team_size?: number }
  ) =>
    apiClient
      .post<Category>(`/api/v1/competitions/${competitionId}/categories`, data)
      .then((r) => r.data),

  update: (
    competitionId: number,
    categoryId: number,
    data: Partial<{ name: string; category_type: string; max_team_size: number; is_active: boolean }>
  ) =>
    apiClient
      .patch<Category>(`/api/v1/competitions/${competitionId}/categories/${categoryId}`, data)
      .then((r) => r.data),

  deactivate: (competitionId: number, categoryId: number) =>
    apiClient.delete(`/api/v1/competitions/${competitionId}/categories/${categoryId}`),
};

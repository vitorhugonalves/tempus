import apiClient from "./client";
import type { Competition } from "../types";

export interface CompetitionCreate {
  name: string;
  location?: string;
  event_date?: string;
  modality?: string;
  max_athletes?: number;
  rules?: string;
}

export interface CompetitionUpdate extends Partial<CompetitionCreate> {
  status?: string;
}

export const competitionsApi = {
  list: (skip = 0, limit = 100) =>
    apiClient.get<Competition[]>("/api/v1/competitions", { params: { skip, limit } }),

  get: (id: number) => apiClient.get<Competition>(`/api/v1/competitions/${id}`),

  create: (data: CompetitionCreate) =>
    apiClient.post<Competition>("/api/v1/competitions", data),

  update: (id: number, data: CompetitionUpdate) =>
    apiClient.patch<Competition>(`/api/v1/competitions/${id}`, data),

  getRanking: (id: number, categoryId?: number) =>
    apiClient.get(`/api/v1/competitions/${id}/ranking`, {
      params: categoryId ? { category_id: categoryId } : undefined,
    }),
};

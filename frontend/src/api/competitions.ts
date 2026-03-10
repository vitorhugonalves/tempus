import apiClient from "./client";
import type { Competition, RankingEntry } from "../types";

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

  getById: (id: number) =>
    apiClient.get<Competition>(`/api/v1/competitions/${id}`).then((r) => r.data),

  create: (data: CompetitionCreate) =>
    apiClient.post<Competition>("/api/v1/competitions", data),

  update: (id: number, data: CompetitionUpdate) =>
    apiClient.patch<Competition>(`/api/v1/competitions/${id}`, data),

  clone: (id: number) =>
    apiClient.post<Competition>(`/api/v1/competitions/${id}/clone`),

  delete: (id: number) =>
    apiClient.delete(`/api/v1/competitions/${id}`),

  getRanking: (id: number, categoryId?: number) =>
    apiClient.get<RankingEntry[]>(`/api/v1/competitions/${id}/ranking`, {
      params: categoryId ? { category_id: categoryId } : undefined,
    }),
};

import apiClient from "./client";
import type { Competition, RankingEntry } from "../types";

export interface MemberInput {
  full_name: string;
  email: string;
}

export interface CompetitorRegisterRequest {
  category_id: number;
  document?: string;
  box_name?: string;
  team_name?: string;
  additional_members?: MemberInput[];
}

export interface CompetitorRegisterResponse {
  registration_id: number;
  team_id: number;
  team_name: string;
  accounts_created: number;
}

export interface CompetitionCreate {
  name: string;
  location?: string;
  event_date?: string;
  modality_id?: number;
  duration_seconds?: number;
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

  register: (id: number, data: CompetitorRegisterRequest) =>
    apiClient.post<CompetitorRegisterResponse>(`/api/v1/competitions/${id}/register`, data),

  getMyRegistration: (id: number) =>
    apiClient.get<{ is_registered: boolean; competition_id: number }>(`/api/v1/competitions/${id}/my-registration`),
};

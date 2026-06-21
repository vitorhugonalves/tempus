import apiClient from "./client";
import type { Competition, EventType, RankingEntry, ScoringModel, TiebreakCriterion, Wod, WodType } from "../types";

export interface WodCreate {
  name: string;
  wod_type: WodType;
  duration_minutes?: number | null;
  description?: string | null;
  order?: number;
  category_ids?: number[];
}

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
  start_date?: string;
  end_date?: string;
  event_type?: EventType;
  is_public?: boolean;
  scoring_model?: ScoringModel;
  tiebreak_criterion?: TiebreakCriterion;
  description?: string;
  regulations_url?: string;
  registration_url?: string;
  instagram_url?: string;
  whatsapp_url?: string;
}

export interface CompetitionUpdate extends Partial<CompetitionCreate> {
  status?: "draft" | "active" | "finished";
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

  uploadLogo: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post(`/api/v1/competitions/${id}/logo`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  uploadBanner: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post(`/api/v1/competitions/${id}/banner`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  listWods: (competitionId: number) =>
    apiClient.get<Wod[]>(`/api/v1/competitions/${competitionId}/wods`),

  createWod: (competitionId: number, data: WodCreate) =>
    apiClient.post<Wod>(`/api/v1/competitions/${competitionId}/wods`, data),

  deleteWod: (competitionId: number, wodId: number) =>
    apiClient.delete(`/api/v1/competitions/${competitionId}/wods/${wodId}`),
};

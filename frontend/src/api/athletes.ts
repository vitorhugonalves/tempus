import apiClient from "./client";
import type { Athlete, AthleteCreate, AthleteBulkResult } from "../types";

export const athletesApi = {
  list: (competitionId: number, params?: { category_id?: number; team_id?: number }) =>
    apiClient.get<Athlete[]>(`/api/v1/competitions/${competitionId}/athletes`, { params }),

  create: (competitionId: number, data: AthleteCreate) =>
    apiClient.post<Athlete>(`/api/v1/competitions/${competitionId}/athletes`, data),

  update: (competitionId: number, athleteId: number, data: Partial<AthleteCreate>) =>
    apiClient.put<Athlete>(`/api/v1/competitions/${competitionId}/athletes/${athleteId}`, data),

  delete: (competitionId: number, athleteId: number) =>
    apiClient.delete(`/api/v1/competitions/${competitionId}/athletes/${athleteId}`),

  importCsv: (competitionId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<AthleteBulkResult>(
      `/api/v1/competitions/${competitionId}/athletes/import`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
  },
};

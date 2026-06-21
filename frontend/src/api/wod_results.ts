import apiClient from "./client";
import type { WodLeaderboard, WodResult, WodResultsData } from "../types";

export interface WodResultUpsert {
  wod_id: number;
  team_id: number;
  time_seconds?: number | null;
  reps?: number | null;
  notes?: string | null;
}

export const wodResultsApi = {
  getData: (competitionId: number) =>
    apiClient
      .get<WodResultsData>(`/api/v1/competitions/${competitionId}/wod-results`)
      .then((r) => r.data),

  upsert: (competitionId: number, data: WodResultUpsert) =>
    apiClient
      .post<WodResult>(`/api/v1/competitions/${competitionId}/wod-results`, data)
      .then((r) => r.data),

  delete: (competitionId: number, resultId: number) =>
    apiClient.delete(
      `/api/v1/competitions/${competitionId}/wod-results/${resultId}`
    ),

  getLeaderboard: (competitionId: number) =>
    apiClient
      .get<WodLeaderboard>(
        `/api/v1/competitions/${competitionId}/wod-leaderboard`
      )
      .then((r) => r.data),
};

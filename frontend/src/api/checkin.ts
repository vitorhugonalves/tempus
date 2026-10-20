import apiClient from "./client";
import type { Athlete, CheckinCandidate } from "../types";

export const checkinApi = {
  search: (competitionId: number, q: string) =>
    apiClient
      .get<CheckinCandidate[]>(`/api/v1/competitions/${competitionId}/checkin/search`, {
        params: { q },
      })
      .then((r) => r.data),

  ensure: (competitionId: number, kind: "athlete" | "registration", sourceId: number) =>
    apiClient
      .post<Athlete>(`/api/v1/competitions/${competitionId}/checkin/ensure`, {
        kind,
        source_id: sourceId,
      })
      .then((r) => r.data),
};

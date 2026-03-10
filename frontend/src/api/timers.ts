import apiClient from "./client";
import type { Penalty, PenaltyType, RankingEntry, Timer, TimerEvent } from "../types";

export const timersApi = {
  list: (competitionId: number) =>
    apiClient.get<Timer[]>(`/api/v1/competitions/${competitionId}/timers`).then((r) => r.data),

  get: (timerId: number) =>
    apiClient.get<Timer>(`/api/v1/timers/${timerId}`).then((r) => r.data),

  create: (data: { competition_id: number; user_id?: number; team_id?: number; category_id?: number }) =>
    apiClient.post<Timer>("/api/v1/timers", data).then((r) => r.data),

  start: (timerId: number, note?: string) =>
    apiClient.post<Timer>(`/api/v1/timers/${timerId}/start`, { note }).then((r) => r.data),

  stop: (timerId: number, note?: string) =>
    apiClient.post<Timer>(`/api/v1/timers/${timerId}/stop`, { note }).then((r) => r.data),

  finish: (timerId: number, note?: string) =>
    apiClient.post<Timer>(`/api/v1/timers/${timerId}/finish`, { note }).then((r) => r.data),

  restart: (timerId: number, note: string) =>
    apiClient.post<Timer>(`/api/v1/timers/${timerId}/restart`, { note }).then((r) => r.data),

  events: (timerId: number) =>
    apiClient.get<TimerEvent[]>(`/api/v1/timers/${timerId}/events`).then((r) => r.data),

  penalties: (timerId: number) =>
    apiClient.get<Penalty[]>(`/api/v1/timers/${timerId}/penalties`).then((r) => r.data),

  applyPenalty: (timerId: number, data: { penalty_type_id: number; justification: string }) =>
    apiClient.post<Penalty>(`/api/v1/timers/${timerId}/penalties`, data).then((r) => r.data),
};

export const penaltyTypesApi = {
  list: (competitionId: number) =>
    apiClient.get<PenaltyType[]>(`/api/v1/competitions/${competitionId}/penalty-types`).then((r) => r.data),

  create: (competitionId: number, data: { name: string; kind: string; seconds: number; description?: string }) =>
    apiClient.post<PenaltyType>(`/api/v1/competitions/${competitionId}/penalty-types`, data).then((r) => r.data),
};

export const rankingApi = {
  get: (competitionId: number, categoryId?: number) => {
    const params = categoryId ? { category_id: categoryId } : {};
    return apiClient.get<RankingEntry[]>(`/api/v1/competitions/${competitionId}/ranking`, { params }).then((r) => r.data);
  },

  exportCsvUrl: (competitionId: number) =>
    `/api/v1/competitions/${competitionId}/export/csv`,

  exportPdfUrl: (competitionId: number) =>
    `/api/v1/competitions/${competitionId}/export/pdf`,

  certificateUrl: (competitionId: number, userId: number) =>
    `/api/v1/competitions/${competitionId}/certificate/${userId}`,

  socialImageUrl: (competitionId: number, userId: number) =>
    `/api/v1/competitions/${competitionId}/social-image/${userId}`,
};

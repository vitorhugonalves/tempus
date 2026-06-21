import apiClient from "./client";
import type { Heat } from "../types";

export interface HeatCreate {
  name: string;
  scheduled_at?: string;
  max_participants?: number;
}

export const heatsApi = {
  list: (competitionId: number) =>
    apiClient
      .get<Heat[]>(`/api/v1/competitions/${competitionId}/heats`)
      .then((r) => r.data),

  create: (competitionId: number, data: HeatCreate) =>
    apiClient
      .post<Heat>(`/api/v1/competitions/${competitionId}/heats`, data)
      .then((r) => r.data),

  delete: (competitionId: number, heatId: number) =>
    apiClient.delete(`/api/v1/competitions/${competitionId}/heats/${heatId}`),

  addTimer: (competitionId: number, heatId: number, timerId: number) =>
    apiClient
      .post<Heat>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}/timers`,
        { timer_id: timerId }
      )
      .then((r) => r.data),

  removeTimer: (competitionId: number, heatId: number, timerId: number) =>
    apiClient.delete(
      `/api/v1/competitions/${competitionId}/heats/${heatId}/timers/${timerId}`
    ),

  addTeam: (competitionId: number, heatId: number, teamId: number) =>
    apiClient
      .post<Heat>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}/teams`,
        { team_id: teamId }
      )
      .then((r) => r.data),

  removeTeam: (competitionId: number, heatId: number, teamId: number) =>
    apiClient.delete(
      `/api/v1/competitions/${competitionId}/heats/${heatId}/teams/${teamId}`
    ),

  start: (competitionId: number, heatId: number) =>
    apiClient
      .post<Heat>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}/start`
      )
      .then((r) => r.data),

  finish: (competitionId: number, heatId: number) =>
    apiClient
      .post<Heat>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}/finish`
      )
      .then((r) => r.data),

  startTeam: (competitionId: number, heatId: number, teamId: number) =>
    apiClient
      .post<Heat>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}/teams/${teamId}/start`
      )
      .then((r) => r.data),

  update: (competitionId: number, heatId: number, name: string) =>
    apiClient
      .patch<Heat>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}`,
        { name }
      )
      .then((r) => r.data),

  move: (competitionId: number, heatId: number, direction: "up" | "down") =>
    apiClient
      .patch<Heat[]>(
        `/api/v1/competitions/${competitionId}/heats/${heatId}/move`,
        { direction }
      )
      .then((r) => r.data),
};

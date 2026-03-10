import apiClient from "./client";
import type { Team, TeamMember } from "../types";

export interface TeamCreate {
  name: string;
  category_id: number;
  captain_id?: number;
}

export interface TeamUpdate {
  name?: string;
  category_id?: number;
  captain_id?: number;
}

export const teamsApi = {
  list: (competitionId: number) =>
    apiClient
      .get<Team[]>(`/api/v1/competitions/${competitionId}/teams`)
      .then((r) => r.data),

  create: (competitionId: number, data: TeamCreate) =>
    apiClient
      .post<Team>(`/api/v1/competitions/${competitionId}/teams`, data)
      .then((r) => r.data),

  update: (competitionId: number, teamId: number, data: TeamUpdate) =>
    apiClient
      .patch<Team>(`/api/v1/competitions/${competitionId}/teams/${teamId}`, data)
      .then((r) => r.data),

  delete: (competitionId: number, teamId: number) =>
    apiClient.delete(`/api/v1/competitions/${competitionId}/teams/${teamId}`),

  listMembers: (competitionId: number, teamId: number) =>
    apiClient
      .get<TeamMember[]>(
        `/api/v1/competitions/${competitionId}/teams/${teamId}/members`
      )
      .then((r) => r.data),

  addMember: (competitionId: number, teamId: number, userId: number) =>
    apiClient
      .post<TeamMember>(
        `/api/v1/competitions/${competitionId}/teams/${teamId}/members`,
        { user_id: userId }
      )
      .then((r) => r.data),

  removeMember: (competitionId: number, teamId: number, userId: number) =>
    apiClient.delete(
      `/api/v1/competitions/${competitionId}/teams/${teamId}/members/${userId}`
    ),
};

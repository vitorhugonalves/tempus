import apiClient from "./client";
import type { User } from "../types";

export interface UserCreate {
  full_name: string;
  email: string;
  password: string;
  role: string;
}

export interface UserUpdate {
  full_name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export const usersApi = {
  list: (skip = 0, limit = 100) =>
    apiClient.get<User[]>("/api/v1/users", { params: { skip, limit } }),

  get: (id: number) => apiClient.get<User>(`/api/v1/users/${id}`),

  create: (data: UserCreate) => apiClient.post<User>("/api/v1/users", data),

  update: (id: number, data: UserUpdate) =>
    apiClient.patch<User>(`/api/v1/users/${id}`, data),
};

import apiClient from "./client";
import type { LoginRequest, LoginResponse } from "../types";

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>("/api/v1/auth/login", data),

  logout: () => apiClient.post("/api/v1/auth/logout"),

  me: () => apiClient.get<LoginResponse>("/api/v1/auth/me"),
};

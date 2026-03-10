import apiClient from "./client";
import type { LoginRequest, LoginResponse } from "../types";

interface RegisterViaInviteRequest {
  token: string;
  full_name: string;
  email: string;
  password: string;
}

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>("/api/v1/auth/login", data),

  logout: () => apiClient.post("/api/v1/auth/logout"),

  me: () => apiClient.get<LoginResponse>("/api/v1/auth/me"),

  forgotPassword: (email: string) =>
    apiClient.post("/api/v1/auth/forgot-password", { email }),

  resetPassword: (token: string, new_password: string) =>
    apiClient.post("/api/v1/auth/reset-password", { token, new_password }),

  registerViaInvite: (data: RegisterViaInviteRequest) =>
    apiClient.post<LoginResponse>("/api/v1/auth/register", data),
};

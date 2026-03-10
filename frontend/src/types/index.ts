export type UserRole = "competitor" | "judge" | "operator" | "admin";

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export type CompetitionStatus = "draft" | "active" | "finished";

export interface Competition {
  id: number;
  name: string;
  location: string | null;
  event_date: string | null;
  modality: string | null;
  max_athletes: number;
  status: CompetitionStatus;
  rules: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
}

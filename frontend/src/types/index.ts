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
  created_at: string;
  updated_at: string;
}

export type CategoryType = "individual" | "team";

export interface Category {
  id: number;
  competition_id: number;
  name: string;
  category_type: CategoryType;
  max_team_size: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type TimerStatus = "idle" | "running" | "stopped" | "finished";

export interface Timer {
  id: number;
  competition_id: number;
  category_id: number | null;
  user_id: number | null;
  team_id: number | null;
  status: TimerStatus;
  started_at: string | null;
  stopped_at: string | null;
  elapsed_seconds: number;
  total_penalty_seconds: number;
  final_seconds: number;
  created_at: string;
  updated_at: string;
}

export type TimerEventType = "start" | "stop" | "restart" | "finish";

export interface TimerEvent {
  id: number;
  timer_id: number;
  event_type: TimerEventType;
  triggered_by_id: number | null;
  note: string | null;
  created_at: string;
}

export interface PenaltyType {
  id: number;
  competition_id: number;
  name: string;
  kind: "time_increment" | "mandatory_stop";
  seconds: number;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Penalty {
  id: number;
  timer_id: number;
  penalty_type_id: number;
  penalty_type_name: string;
  applied_by_id: number | null;
  justification: string;
  seconds_added: number;
  created_at: string;
}

export interface RankingEntry {
  position: number;
  timer_id: number;
  user_id: number | null;
  team_id: number | null;
  athlete_name: string;
  category_name: string | null;
  elapsed_seconds: number;
  total_penalty_seconds: number;
  final_seconds: number;
  status: TimerStatus;
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

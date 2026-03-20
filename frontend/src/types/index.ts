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
  modality_id: number | null;
  modality_name: string | null;
  duration_seconds: number | null;
  max_athletes: number;
  status: CompetitionStatus;
  rules: string | null;
  created_at: string;
  updated_at: string;
}

export interface Modality {
  id: number;
  name: string;
  description: string | null;
  default_duration_seconds: number | null;
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

export type HeatStatus = "pending" | "running" | "finished";

export interface HeatTeamRef {
  team_id: number;
  team_name: string;
}

export interface Heat {
  id: number;
  competition_id: number;
  name: string;
  status: HeatStatus;
  scheduled_at: string | null;
  max_participants: number | null;
  timer_count: number;
  team_count: number;
  teams: HeatTeamRef[];
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  id: number;
  team_id: number;
  user_id: number;
  user_name: string;
  created_at: string;
}

export interface Team {
  id: number;
  competition_id: number;
  category_id: number;
  name: string;
  box_name: string | null;
  captain_id: number | null;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export type TimerStatus =
  | "created"
  | "ready"
  | "running"
  | "paused"
  | "finished"
  | "cancelled";

export interface Timer {
  id: number;
  competition_id: number;
  category_id: number | null;
  user_id: number | null;
  team_id: number | null;
  heat_id: number | null;
  status: TimerStatus;
  elapsed_seconds: number;
  accumulated_ms: number;
  started_at_ms: number | null;
  total_penalty_seconds: number;
  final_seconds: number;
  created_at: string;
  updated_at: string;
}

export type TimerEventType =
  | "started"
  | "paused"
  | "resumed"
  | "finished"
  | "reset"
  | "cancelled"
  | "ready"
  | "adjusted"
  | "split";

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
  team_name: string | null;
  box_name: string | null;
  category_name: string | null;
  elapsed_seconds: number;
  total_penalty_seconds: number;
  final_seconds: number;
  infractions_count: number;
  remaining_seconds: number | null;
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

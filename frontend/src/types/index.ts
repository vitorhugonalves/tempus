export type UserRole = "competitor" | "judge" | "operator" | "admin";

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export type CompetitionStatus = "draft" | "active" | "finished";
export type EventType = "hyrox" | "crossfit";
export type ScoringModel = "lowest_time" | "most_points";
export type TiebreakCriterion = "last_checkpoint" | "registration_date" | "alphabetical";
export type Gender = "male" | "female" | "mixed";
export type TshirtSize = "P" | "M" | "G" | "GG" | "XG";

export interface Competition {
  id: number;
  name: string;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  event_type: EventType | null;
  is_public: boolean;
  scoring_model: ScoringModel | null;
  tiebreak_criterion: TiebreakCriterion | null;
  status: CompetitionStatus;
  description?: string | null;
  regulations_url?: string | null;
  registration_url?: string | null;
  instagram_url?: string | null;
  whatsapp_url?: string | null;
  has_logo?: boolean;
  has_banner?: boolean;
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
  gender: Gender | null;
  age_restriction_enabled: boolean;
  age_min: number | null;
  age_max: number | null;
  max_team_size: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Athlete {
  id: number;
  competition_id: number;
  category_id: number | null;
  team_id: number | null;
  team_name: string | null;
  name: string;
  email: string | null;
  document: string | null;
  phone: string | null;
  tshirt_size: TshirtSize | null;
  created_at: string;
  updated_at: string;
}

export interface AthleteCreate {
  name: string;
  email?: string;
  document?: string;
  phone?: string;
  category_id?: number;
  team_id?: number;
  tshirt_size?: TshirtSize;
}

export interface AthleteBulkResult {
  created: number;
  errors: Array<{ row: number; name: string; error: string }>;
}

export interface CepResult {
  cep: string | null;
  logradouro: string | null;
  complemento: string | null;
  bairro: string | null;
  localidade: string | null;
  uf: string | null;
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
  sort_order: number;
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

export interface TeamBulkError {
  row: number;
  name: string;
  error: string;
}

export interface TeamBulkResult {
  created: number;
  errors: TeamBulkError[];
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

export interface CrossfitRankingEntry {
  position: number;
  team_id: number | null;
  user_id: number | null;
  athlete_name: string;
  team_name: string | null;
  category_name: string | null;
  wods_completed: number;
  total_points: number;
  status: string;
}

export type WodType = "amrap" | "for_time" | "emom" | "max_load";

export interface Wod {
  id: number;
  competition_id: number;
  name: string;
  wod_type: WodType;
  duration_minutes: number | null;
  description: string | null;
  order: number;
  category_ids: number[];
  created_at: string;
  updated_at: string;
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

export interface WodResult {
  id: number;
  competition_id: number;
  wod_id: number;
  team_id: number;
  time_seconds: number | null;
  reps: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface WodResultsData {
  wods: Wod[];
  teams: { id: number; name: string; category_id: number }[];
  results: WodResult[];
}

export interface LeaderboardWodEntry {
  wod_id: number;
  wod_name: string;
  time_seconds: number | null;
  reps: number | null;
  points: number;
  rank: number | null;
}

export interface WodLeaderboardEntry {
  position: number;
  team_id: number;
  team_name: string;
  total_points: number;
  wod_entries: LeaderboardWodEntry[];
}

export interface WodLeaderboard {
  scoring_model: string | null;
  entries: WodLeaderboardEntry[];
}

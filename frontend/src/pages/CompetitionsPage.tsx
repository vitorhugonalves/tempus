// @ts-nocheck — arquivo legado substituído por CompetitionsListPage; mantido para histórico
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  PlusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from "@heroicons/react/24/outline";
import { competitionsApi, type CompetitionCreate } from "../api/competitions";
import { categoriesApi } from "../api/categories";
import { penaltyTypesApi } from "../api/timers";
import { modalitiesApi } from "../api/modalities";
import { teamsApi, type TeamCreate } from "../api/teams";
import { heatsApi, type HeatCreate } from "../api/heats";
import { authApi } from "../api/auth";
import { usersApi } from "../api/users";
import { useAuthStore } from "../store/auth";
import { Card, CardHeader } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type {
  Category,
  Competition,
  Heat,
  HeatTeamRef,
  Modality,
  PenaltyType,
  Team,
  TeamMember,
  User,
} from "../types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_BADGE: Record<
  string,
  { label: string; variant: "gray" | "green" | "red" }
> = {
  draft: { label: "Rascunho", variant: "gray" },
  active: { label: "Ativa", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

const HEAT_STATUS_BADGE: Record<
  string,
  { label: string; variant: "gray" | "green" | "red" }
> = {
  pending: { label: "Pendente", variant: "gray" },
  running: { label: "Em andamento", variant: "green" },
  finished: { label: "Finalizado", variant: "red" },
};

const INITIAL_FORM: CompetitionCreate = {
  name: "",
  location: "",
  event_date: "",
  modality_id: undefined,
  duration_seconds: undefined,
  max_athletes: 300,
};

// ---------------------------------------------------------------------------
// Helpers: duration HH:MM:SS
// ---------------------------------------------------------------------------
function secondsToHms(seconds: number): { h: number; m: number; s: number } {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return { h, m, s };
}

function hmsToSeconds(h: number, m: number, s: number): number {
  return h * 3600 + m * 60 + s;
}

function formatHms(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null) return "—";
  const { h, m, s } = secondsToHms(totalSeconds);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

// ---------------------------------------------------------------------------
// Helpers: date Brazilian format dd/mm/aaaa
// ---------------------------------------------------------------------------
function ptDateToIso(ptDate: string): string {
  // "dd/mm/aaaa" → "yyyy-mm-dd"
  const match = ptDate.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return ptDate;
  return `${match[3]}-${match[2]}-${match[1]}`;
}

function isoToPtDate(iso: string): string {
  // "yyyy-mm-dd" → "dd/mm/aaaa"
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

// ---------------------------------------------------------------------------
// Helper: format ISO date as dd/mm/yyyy (for display in table)
// ---------------------------------------------------------------------------
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR");
}

// ---------------------------------------------------------------------------
// Sub-component: HmsDurationInput
// ---------------------------------------------------------------------------
interface HmsDurationInputProps {
  valueSeconds: number | undefined;
  onChange: (seconds: number | undefined) => void;
  label?: string;
}

function HmsDurationInput({ valueSeconds, onChange, label }: HmsDurationInputProps) {
  const parsed = valueSeconds != null ? secondsToHms(valueSeconds) : { h: 0, m: 0, s: 0 };
  const isEmpty = valueSeconds == null;

  const [h, setH] = useState<number | "">(isEmpty ? "" : parsed.h);
  const [m, setM] = useState<number | "">(isEmpty ? "" : parsed.m);
  const [s, setS] = useState<number | "">(isEmpty ? "" : parsed.s);

  // Sync when external value changes (e.g. modality auto-fill)
  useEffect(() => {
    if (valueSeconds == null) {
      setH("");
      setM("");
      setS("");
    } else {
      const p = secondsToHms(valueSeconds);
      setH(p.h);
      setM(p.m);
      setS(p.s);
    }
  }, [valueSeconds]);

  function handleChange(
    newH: number | "",
    newM: number | "",
    newS: number | ""
  ) {
    if (newH === "" && newM === "" && newS === "") {
      onChange(undefined);
    } else {
      onChange(hmsToSeconds(Number(newH || 0), Number(newM || 0), Number(newS || 0)));
    }
  }

  const inputClass =
    "w-16 rounded-lg border border-gray-300 px-2 py-2 text-sm text-gray-900 text-center focus:outline-none focus:ring-2 focus:ring-primary-500";

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      )}
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          max={99}
          className={inputClass}
          placeholder="HH"
          value={h}
          onChange={(e) => {
            const val = e.target.value === "" ? "" : Number(e.target.value);
            setH(val);
            handleChange(val, m, s);
          }}
        />
        <span className="text-gray-400 font-bold">:</span>
        <input
          type="number"
          min={0}
          max={59}
          className={inputClass}
          placeholder="MM"
          value={m}
          onChange={(e) => {
            const val = e.target.value === "" ? "" : Number(e.target.value);
            setM(val);
            handleChange(h, val, s);
          }}
        />
        <span className="text-gray-400 font-bold">:</span>
        <input
          type="number"
          min={0}
          max={59}
          className={inputClass}
          placeholder="SS"
          value={s}
          onChange={(e) => {
            const val = e.target.value === "" ? "" : Number(e.target.value);
            setS(val);
            handleChange(h, m, val);
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: CategoryRow — inline-editable row
// ---------------------------------------------------------------------------
interface CategoryRowProps {
  competitionId: number;
  category: Category;
  canManage: boolean;
  onUpdated: () => void;
}

function CategoryRow({
  competitionId,
  category,
  canManage,
  onUpdated,
}: CategoryRowProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [categoryType, setCategoryType] = useState(category.category_type);
  const [maxTeamSize, setMaxTeamSize] = useState<number | "">(
    category.max_team_size ?? ""
  );
  const [saving, setSaving] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setError(null);
    setSaving(true);
    try {
      await categoriesApi.update(competitionId, category.id, {
        name,
        category_type: categoryType,
        max_team_size:
          categoryType === "team" && maxTeamSize !== "" ? Number(maxTeamSize) : undefined,
      });
      setEditing(false);
      onUpdated();
    } catch {
      setError("Erro ao salvar categoria.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate() {
    if (!confirm(`Desativar a categoria "${category.name}"?`)) return;
    setDeactivating(true);
    try {
      await categoriesApi.deactivate(competitionId, category.id);
      onUpdated();
    } catch {
      setError("Erro ao desativar categoria.");
    } finally {
      setDeactivating(false);
    }
  }

  return (
    <tr className="border-t border-gray-100 hover:bg-gray-50 transition-colors">
      {editing ? (
        <>
          <td className="px-4 py-2">
            <input
              className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </td>
          <td className="px-4 py-2">
            <select
              className="rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              value={categoryType}
              onChange={(e) => setCategoryType(e.target.value as "individual" | "team")}
            >
              <option value="individual">Individual</option>
              <option value="team">Equipe</option>
            </select>
          </td>
          <td className="px-4 py-2">
            {categoryType === "team" ? (
              <input
                type="number"
                min={2}
                className="w-20 rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={maxTeamSize}
                onChange={(e) =>
                  setMaxTeamSize(e.target.value === "" ? "" : Number(e.target.value))
                }
              />
            ) : (
              <span className="text-gray-400 text-xs">—</span>
            )}
          </td>
          <td className="px-4 py-2">
            <Badge variant={category.is_active ? "green" : "gray"}>
              {category.is_active ? "Ativa" : "Inativa"}
            </Badge>
          </td>
          <td className="px-4 py-2">
            <div className="flex items-center gap-2 flex-wrap">
              {error && <span className="text-xs text-red-600">{error}</span>}
              <Button size="sm" variant="primary" isLoading={saving} onClick={handleSave}>
                Salvar
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setEditing(false);
                  setName(category.name);
                  setCategoryType(category.category_type);
                  setMaxTeamSize(category.max_team_size ?? "");
                  setError(null);
                }}
              >
                Cancelar
              </Button>
            </div>
          </td>
        </>
      ) : (
        <>
          <td className="px-4 py-2 text-sm font-medium text-gray-900">{category.name}</td>
          <td className="px-4 py-2 text-sm text-gray-600 capitalize">
            {category.category_type === "individual" ? "Individual" : "Equipe"}
          </td>
          <td className="px-4 py-2 text-sm text-gray-600">
            {category.category_type === "team" ? (category.max_team_size ?? "—") : "—"}
          </td>
          <td className="px-4 py-2">
            <Badge variant={category.is_active ? "green" : "gray"}>
              {category.is_active ? "Ativa" : "Inativa"}
            </Badge>
          </td>
          <td className="px-4 py-2">
            {canManage && category.is_active && (
              <div className="flex items-center gap-2">
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                  Editar
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  isLoading={deactivating}
                  onClick={handleDeactivate}
                >
                  Desativar
                </Button>
              </div>
            )}
          </td>
        </>
      )}
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: ManagementPanel
// ---------------------------------------------------------------------------
interface ManagementPanelProps {
  competition: Competition;
  canManage: boolean;
  isAdmin: boolean;
  onStatusChanged: () => void;
}

type PanelTab = "categories" | "penalties" | "invite" | "teams" | "heats";

function ManagementPanel({
  competition,
  canManage,
  onStatusChanged,
}: ManagementPanelProps) {
  const [activeTab, setActiveTab] = useState<PanelTab>("categories");

  // Status change
  const [statusSaving, setStatusSaving] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  // Categories
  const [categories, setCategories] = useState<Category[]>([]);
  const [catLoading, setCatLoading] = useState(true);
  const [newCatName, setNewCatName] = useState("");
  const [newCatType, setNewCatType] = useState<"individual" | "team">("individual");
  const [newCatMaxTeam, setNewCatMaxTeam] = useState<number | "">("");
  const [catSaving, setCatSaving] = useState(false);
  const [catError, setCatError] = useState<string | null>(null);
  const [catSuccess, setCatSuccess] = useState<string | null>(null);

  // Penalty types
  const [penalties, setPenalties] = useState<PenaltyType[]>([]);
  const [penLoading, setPenLoading] = useState(false);
  const [newPenName, setNewPenName] = useState("");
  const [newPenKind, setNewPenKind] = useState<"time_increment" | "mandatory_stop">("time_increment");
  const [newPenSeconds, setNewPenSeconds] = useState<number | "">("");
  const [penSaving, setPenSaving] = useState(false);
  const [penError, setPenError] = useState<string | null>(null);
  const [penSuccess, setPenSuccess] = useState<string | null>(null);

  // Invite
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteCategoryId, setInviteCategoryId] = useState<number | "">("");
  const [inviteTeamId, setInviteTeamId] = useState<number | "">("");
  const [inviteSaving, setInviteSaving] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  // Teams
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamCategoryId, setNewTeamCategoryId] = useState<number | "">("");
  const [teamSaving, setTeamSaving] = useState(false);
  const [teamError, setTeamError] = useState<string | null>(null);
  const [teamSuccess, setTeamSuccess] = useState<string | null>(null);

  // Teams: member management
  const [expandedTeamId, setExpandedTeamId] = useState<number | null>(null);
  const [teamMembers, setTeamMembers] = useState<Record<number, TeamMember[]>>({});
  const [teamMembersLoading, setTeamMembersLoading] = useState<Record<number, boolean>>({});
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [addMemberUserId, setAddMemberUserId] = useState<number | "">("");
  const [memberActionError, setMemberActionError] = useState<string | null>(null);

  // Heats
  const [heats, setHeats] = useState<Heat[]>([]);
  const [heatsLoading, setHeatsLoading] = useState(false);
  const [newHeatName, setNewHeatName] = useState("");
  const [newHeatMaxParticipants, setNewHeatMaxParticipants] = useState<number | "">("");
  const [heatSaving, setHeatSaving] = useState(false);
  const [heatError, setHeatError] = useState<string | null>(null);
  const [heatSuccess, setHeatSuccess] = useState<string | null>(null);

  // Heats: team association
  const [expandedHeatId, setExpandedHeatId] = useState<number | null>(null);
  const [heatTeamActionError, setHeatTeamActionError] = useState<string | null>(null);
  const [addHeatTeamId, setAddHeatTeamId] = useState<number | "">("");

  async function loadCategories() {
    setCatLoading(true);
    try {
      const data = await categoriesApi.list(competition.id);
      setCategories(data);
    } finally {
      setCatLoading(false);
    }
  }

  async function loadPenalties() {
    setPenLoading(true);
    try {
      const data = await penaltyTypesApi.list(competition.id);
      setPenalties(data);
    } finally {
      setPenLoading(false);
    }
  }

  async function loadTeams() {
    setTeamsLoading(true);
    try {
      const data = await teamsApi.list(competition.id);
      setTeams(data);
    } finally {
      setTeamsLoading(false);
    }
  }

  async function loadHeats() {
    setHeatsLoading(true);
    try {
      const data = await heatsApi.list(competition.id);
      setHeats(data);
    } finally {
      setHeatsLoading(false);
    }
  }

  async function loadAllUsers() {
    try {
      const res = await usersApi.list(0, 500);
      setAllUsers(res.data);
    } catch {
      // non-critical
    }
  }

  async function loadTeamMembers(teamId: number) {
    setTeamMembersLoading((prev) => ({ ...prev, [teamId]: true }));
    try {
      const data = await teamsApi.listMembers(competition.id, teamId);
      setTeamMembers((prev) => ({ ...prev, [teamId]: data }));
    } finally {
      setTeamMembersLoading((prev) => ({ ...prev, [teamId]: false }));
    }
  }

  useEffect(() => {
    loadCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competition.id]);

  useEffect(() => {
    if (activeTab === "penalties" && penalties.length === 0 && !penLoading) {
      loadPenalties();
    }
    if (activeTab === "teams" && teams.length === 0 && !teamsLoading) {
      loadTeams();
      loadAllUsers();
    }
    if (activeTab === "heats" && heats.length === 0 && !heatsLoading) {
      loadHeats();
      // Also load teams if not loaded yet, for heat-team association
      if (teams.length === 0) {
        loadTeams();
      }
    }
    if (activeTab === "invite" && teams.length === 0 && !teamsLoading) {
      loadTeams();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // Status advancement
  async function handleAdvanceStatus(newStatus: "active" | "finished") {
    setStatusSaving(true);
    setStatusError(null);
    try {
      await competitionsApi.update(competition.id, { status: newStatus });
      onStatusChanged();
    } catch {
      setStatusError("Erro ao alterar status da competição.");
    } finally {
      setStatusSaving(false);
    }
  }

  // Add category
  async function handleAddCategory(e: React.FormEvent) {
    e.preventDefault();
    setCatError(null);
    setCatSuccess(null);
    if (!newCatName.trim()) {
      setCatError("O nome da categoria é obrigatório.");
      return;
    }
    setCatSaving(true);
    try {
      await categoriesApi.create(competition.id, {
        name: newCatName.trim(),
        category_type: newCatType,
        max_team_size:
          newCatType === "team" && newCatMaxTeam !== "" ? Number(newCatMaxTeam) : undefined,
      });
      setNewCatName("");
      setNewCatType("individual");
      setNewCatMaxTeam("");
      setCatSuccess("Categoria criada com sucesso.");
      await loadCategories();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (typeof detail === "string") {
        setCatError(detail);
      } else if (Array.isArray(detail) && detail.length > 0) {
        setCatError(String((detail[0] as { msg?: string })?.msg ?? "Erro ao criar categoria."));
      } else {
        setCatError("Erro ao criar categoria.");
      }
    } finally {
      setCatSaving(false);
    }
  }

  // Add penalty type
  async function handleAddPenalty(e: React.FormEvent) {
    e.preventDefault();
    setPenError(null);
    setPenSuccess(null);
    if (!newPenName.trim()) {
      setPenError("O nome do tipo de penalidade é obrigatório.");
      return;
    }
    if (newPenKind === "time_increment" && (newPenSeconds === "" || newPenSeconds <= 0)) {
      setPenError("Informe o número de segundos para penalidades de tempo.");
      return;
    }
    setPenSaving(true);
    try {
      await penaltyTypesApi.create(competition.id, {
        name: newPenName.trim(),
        kind: newPenKind,
        seconds: newPenKind === "time_increment" ? Number(newPenSeconds) : 0,
      });
      setNewPenName("");
      setNewPenKind("time_increment");
      setNewPenSeconds("");
      setPenSuccess("Tipo de penalidade criado com sucesso.");
      await loadPenalties();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPenError(detail ?? "Erro ao criar tipo de penalidade.");
    } finally {
      setPenSaving(false);
    }
  }

  // Send invite
  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setInviteSuccess(null);
    if (!inviteEmail.trim()) {
      setInviteError("Informe o e-mail do atleta.");
      return;
    }
    setInviteSaving(true);
    try {
      await authApi.sendInvite(
        inviteEmail.trim(),
        competition.id,
        inviteCategoryId !== "" ? Number(inviteCategoryId) : undefined,
        inviteTeamId !== "" ? Number(inviteTeamId) : undefined
      );
      setInviteEmail("");
      setInviteCategoryId("");
      setInviteTeamId("");
      setInviteSuccess("Convite enviado com sucesso.");
    } catch {
      setInviteError("Erro ao enviar convite. Verifique o e-mail e tente novamente.");
    } finally {
      setInviteSaving(false);
    }
  }

  // Add team
  async function handleAddTeam(e: React.FormEvent) {
    e.preventDefault();
    setTeamError(null);
    setTeamSuccess(null);
    if (!newTeamName.trim()) {
      setTeamError("O nome da equipe é obrigatório.");
      return;
    }
    if (newTeamCategoryId === "") {
      setTeamError("Selecione uma categoria para a equipe.");
      return;
    }
    setTeamSaving(true);
    try {
      const payload: TeamCreate = {
        name: newTeamName.trim(),
        category_id: Number(newTeamCategoryId),
      };
      await teamsApi.create(competition.id, payload);
      setNewTeamName("");
      setNewTeamCategoryId("");
      setTeamSuccess("Equipe criada com sucesso.");
      await loadTeams();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setTeamError(detail ?? "Erro ao criar equipe.");
    } finally {
      setTeamSaving(false);
    }
  }

  // Toggle team member panel
  async function handleToggleTeamMembers(teamId: number) {
    setMemberActionError(null);
    if (expandedTeamId === teamId) {
      setExpandedTeamId(null);
      return;
    }
    setExpandedTeamId(teamId);
    setAddMemberUserId("");
    if (!teamMembers[teamId]) {
      await loadTeamMembers(teamId);
    }
  }

  // Add member to team
  async function handleAddMember(teamId: number) {
    if (addMemberUserId === "") return;
    setMemberActionError(null);
    try {
      await teamsApi.addMember(competition.id, teamId, Number(addMemberUserId));
      setAddMemberUserId("");
      await loadTeamMembers(teamId);
      await loadTeams();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMemberActionError(detail ?? "Erro ao adicionar membro.");
    }
  }

  // Remove member from team
  async function handleRemoveMember(teamId: number, userId: number, userName: string) {
    if (!confirm(`Remover "${userName}" da equipe?`)) return;
    setMemberActionError(null);
    try {
      await teamsApi.removeMember(competition.id, teamId, userId);
      await loadTeamMembers(teamId);
      await loadTeams();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMemberActionError(detail ?? "Erro ao remover membro.");
    }
  }

  // Add heat
  async function handleAddHeat(e: React.FormEvent) {
    e.preventDefault();
    setHeatError(null);
    setHeatSuccess(null);
    if (!newHeatName.trim()) {
      setHeatError("O nome da bateria é obrigatório.");
      return;
    }
    setHeatSaving(true);
    try {
      const payload: HeatCreate = {
        name: newHeatName.trim(),
        ...(newHeatMaxParticipants !== "" ? { max_participants: Number(newHeatMaxParticipants) } : {}),
      };
      await heatsApi.create(competition.id, payload);
      setNewHeatName("");
      setNewHeatMaxParticipants("");
      setHeatSuccess("Bateria criada com sucesso.");
      await loadHeats();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setHeatError(detail ?? "Erro ao criar bateria.");
    } finally {
      setHeatSaving(false);
    }
  }

  // Start heat
  async function handleStartHeat(heatId: number, heatName: string) {
    if (!confirm(`Iniciar a bateria "${heatName}"?`)) return;
    try {
      await heatsApi.start(competition.id, heatId);
      await loadHeats();
    } catch {
      setHeatError("Erro ao iniciar bateria.");
    }
  }

  // Delete heat
  async function handleDeleteHeat(heatId: number, heatName: string) {
    if (!confirm(`Excluir a bateria "${heatName}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await heatsApi.delete(competition.id, heatId);
      if (expandedHeatId === heatId) setExpandedHeatId(null);
      await loadHeats();
    } catch {
      setHeatError("Erro ao excluir bateria.");
    }
  }

  // Toggle heat team panel
  function handleToggleHeatTeams(heatId: number) {
    setHeatTeamActionError(null);
    setAddHeatTeamId("");
    setExpandedHeatId((prev) => (prev === heatId ? null : heatId));
  }

  // Add team to heat
  async function handleAddTeamToHeat(heatId: number) {
    if (addHeatTeamId === "") return;
    setHeatTeamActionError(null);
    try {
      await heatsApi.addTeam(competition.id, heatId, Number(addHeatTeamId));
      setAddHeatTeamId("");
      await loadHeats();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setHeatTeamActionError(detail ?? "Erro ao adicionar equipe à bateria.");
    }
  }

  // Remove team from heat
  async function handleRemoveTeamFromHeat(heatId: number, teamId: number, teamName: string) {
    if (!confirm(`Remover a equipe "${teamName}" da bateria?`)) return;
    setHeatTeamActionError(null);
    try {
      await heatsApi.removeTeam(competition.id, heatId, teamId);
      await loadHeats();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setHeatTeamActionError(detail ?? "Erro ao remover equipe da bateria.");
    }
  }

  const tabClass = (tab: PanelTab) =>
    [
      "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
      activeTab === tab
        ? "border-primary-600 text-primary-600"
        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
    ].join(" ");

  // Derived: selected category for invite
  const inviteSelectedCategory =
    inviteCategoryId !== ""
      ? categories.find((c) => c.id === Number(inviteCategoryId))
      : null;

  const inviteIsIndividualCategory = inviteSelectedCategory?.category_type === "individual";

  // Teams filtered by invite category for team selector
  const teamsForInviteCategory =
    inviteCategoryId !== ""
      ? teams.filter((t) => t.category_id === Number(inviteCategoryId))
      : teams;

  return (
    <div className="border-t border-gray-100 bg-gray-50 px-6 py-6 space-y-6">
      {/* Status section */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700">Status atual:</span>
          <Badge variant={STATUS_BADGE[competition.status]?.variant ?? "gray"}>
            {STATUS_BADGE[competition.status]?.label ?? competition.status}
          </Badge>
        </div>

        {canManage && competition.status === "draft" && (
          <Button
            size="sm"
            variant="primary"
            isLoading={statusSaving}
            onClick={() => handleAdvanceStatus("active")}
          >
            Iniciar Competição
          </Button>
        )}
        {canManage && competition.status === "active" && (
          <Button
            size="sm"
            variant="danger"
            isLoading={statusSaving}
            onClick={() => handleAdvanceStatus("finished")}
          >
            Encerrar Competição
          </Button>
        )}
        {competition.status === "finished" && (
          <span className="text-sm text-gray-400 italic">Encerrada</span>
        )}

        {statusError && (
          <div className="w-full">
            <Alert variant="error">{statusError}</Alert>
          </div>
        )}

        {/* Quick links */}
        <div className="ml-auto flex items-center gap-3">
          <Link
            to={`/competitions/${competition.id}/timers`}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium underline underline-offset-2"
          >
            Ver Timers
          </Link>
          <Link
            to={`/ranking/${competition.id}`}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium underline underline-offset-2"
          >
            Ver Ranking
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div>
        <div className="flex border-b border-gray-200 mb-4 flex-wrap">
          <button className={tabClass("categories")} onClick={() => setActiveTab("categories")}>
            Categorias
          </button>
          <button className={tabClass("penalties")} onClick={() => setActiveTab("penalties")}>
            Tipos de Penalidade
          </button>
          <button className={tabClass("teams")} onClick={() => setActiveTab("teams")}>
            Equipes
          </button>
          <button className={tabClass("heats")} onClick={() => setActiveTab("heats")}>
            Baterias
          </button>
          <button className={tabClass("invite")} onClick={() => setActiveTab("invite")}>
            Convidar Atleta
          </button>
        </div>

        {/* --- Categories tab --- */}
        {activeTab === "categories" && (
          <div className="space-y-4">
            {catLoading ? (
              <p className="text-sm text-gray-400">Carregando categorias...</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Nome
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Tipo
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Max Atletas
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ações
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.length === 0 ? (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-4 py-6 text-center text-gray-400 text-sm"
                        >
                          Nenhuma categoria cadastrada.
                        </td>
                      </tr>
                    ) : (
                      categories.map((cat) => (
                        <CategoryRow
                          key={cat.id}
                          competitionId={competition.id}
                          category={cat}
                          canManage={canManage}
                          onUpdated={loadCategories}
                        />
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {canManage && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  Adicionar Categoria
                </h3>
                {catError && (
                  <div className="mb-3">
                    <Alert variant="error">{catError}</Alert>
                  </div>
                )}
                {catSuccess && (
                  <div className="mb-3">
                    <Alert variant="success">{catSuccess}</Alert>
                  </div>
                )}
                <form
                  onSubmit={handleAddCategory}
                  className="flex flex-wrap items-end gap-3"
                >
                  <div className="flex-1 min-w-[160px]">
                    <Input
                      label="Nome"
                      value={newCatName}
                      onChange={(e) => setNewCatName(e.target.value)}
                      placeholder="Ex: Elite Masculino"
                      required
                    />
                  </div>
                  <div className="min-w-[140px]">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Tipo
                    </label>
                    <select
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      value={newCatType}
                      onChange={(e) =>
                        setNewCatType(e.target.value as "individual" | "team")
                      }
                    >
                      <option value="individual">Individual</option>
                      <option value="team">Equipe</option>
                    </select>
                  </div>
                  {newCatType === "team" && (
                    <div className="min-w-[100px]">
                      <Input
                        label="Tam. Equipe"
                        type="number"
                        min={2}
                        value={newCatMaxTeam}
                        onChange={(e) =>
                          setNewCatMaxTeam(
                            e.target.value === "" ? "" : Number(e.target.value)
                          )
                        }
                        placeholder="Ex: 4"
                      />
                    </div>
                  )}
                  <Button type="submit" size="sm" variant="primary" isLoading={catSaving}>
                    <PlusIcon className="h-4 w-4" />
                    Adicionar
                  </Button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* --- Penalty types tab --- */}
        {activeTab === "penalties" && (
          <div className="space-y-4">
            {penLoading ? (
              <p className="text-sm text-gray-400">Carregando tipos de penalidade...</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Nome
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Tipo
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Segundos
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {penalties.length === 0 ? (
                      <tr>
                        <td
                          colSpan={3}
                          className="px-4 py-6 text-center text-gray-400 text-sm"
                        >
                          Nenhum tipo de penalidade cadastrado.
                        </td>
                      </tr>
                    ) : (
                      penalties.map((pen) => (
                        <tr
                          key={pen.id}
                          className="border-t border-gray-100 hover:bg-gray-50"
                        >
                          <td className="px-4 py-2 font-medium text-gray-900">
                            {pen.name}
                          </td>
                          <td className="px-4 py-2 text-gray-600">
                            {pen.kind === "time_increment" ? "Tempo" : "Desclassificação"}
                          </td>
                          <td className="px-4 py-2 text-gray-600">
                            {pen.kind === "time_increment" ? pen.seconds : "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {canManage && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  Adicionar Tipo de Penalidade
                </h3>
                {penError && (
                  <div className="mb-3">
                    <Alert variant="error">{penError}</Alert>
                  </div>
                )}
                {penSuccess && (
                  <div className="mb-3">
                    <Alert variant="success">{penSuccess}</Alert>
                  </div>
                )}
                <form
                  onSubmit={handleAddPenalty}
                  className="flex flex-wrap items-end gap-3"
                >
                  <div className="flex-1 min-w-[160px]">
                    <Input
                      label="Nome"
                      value={newPenName}
                      onChange={(e) => setNewPenName(e.target.value)}
                      placeholder="Ex: Penalidade de Burpee"
                      required
                    />
                  </div>
                  <div className="min-w-[160px]">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Tipo
                    </label>
                    <select
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      value={newPenKind}
                      onChange={(e) =>
                        setNewPenKind(e.target.value as "time_increment" | "mandatory_stop")
                      }
                    >
                      <option value="time_increment">Tempo (+segundos)</option>
                      <option value="mandatory_stop">Desclassificação</option>
                    </select>
                  </div>
                  {newPenKind === "time_increment" && (
                    <div className="min-w-[100px]">
                      <Input
                        label="Segundos"
                        type="number"
                        min={1}
                        value={newPenSeconds}
                        onChange={(e) =>
                          setNewPenSeconds(
                            e.target.value === "" ? "" : Number(e.target.value)
                          )
                        }
                        placeholder="Ex: 30"
                      />
                    </div>
                  )}
                  <Button type="submit" size="sm" variant="primary" isLoading={penSaving}>
                    <PlusIcon className="h-4 w-4" />
                    Adicionar
                  </Button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* --- Teams tab --- */}
        {activeTab === "teams" && (
          <div className="space-y-4">
            {memberActionError && (
              <Alert variant="error">{memberActionError}</Alert>
            )}
            {teamsLoading ? (
              <p className="text-sm text-gray-400">Carregando equipes...</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Nome
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Categoria
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Membros
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ações
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {teams.length === 0 ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="px-4 py-6 text-center text-gray-400 text-sm"
                        >
                          Nenhuma equipe cadastrada.
                        </td>
                      </tr>
                    ) : (
                      teams.map((team) => {
                        const cat = categories.find((c) => c.id === team.category_id);
                        const isExpanded = expandedTeamId === team.id;
                        const members = teamMembers[team.id] ?? [];
                        const membersLoading = teamMembersLoading[team.id] ?? false;

                        // Users not already in team
                        const memberUserIds = new Set(members.map((mem) => mem.user_id));
                        const availableUsers = allUsers.filter(
                          (u) => !memberUserIds.has(u.id)
                        );

                        return (
                          <React.Fragment key={team.id}>
                            <tr className="border-t border-gray-100 hover:bg-gray-50">
                              <td className="px-4 py-2 font-medium text-gray-900">
                                {team.name}
                              </td>
                              <td className="px-4 py-2 text-gray-600">
                                {cat?.name ?? "—"}
                              </td>
                              <td className="px-4 py-2 text-gray-600">
                                {team.member_count}
                              </td>
                              <td className="px-4 py-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                  {canManage && (
                                    <Button
                                      size="sm"
                                      variant={isExpanded ? "primary" : "secondary"}
                                      onClick={() => handleToggleTeamMembers(team.id)}
                                    >
                                      Gerenciar Membros
                                      {isExpanded ? (
                                        <ChevronUpIcon className="h-3.5 w-3.5" />
                                      ) : (
                                        <ChevronDownIcon className="h-3.5 w-3.5" />
                                      )}
                                    </Button>
                                  )}
                                  {canManage && (
                                    <Button
                                      size="sm"
                                      variant="danger"
                                      onClick={async () => {
                                        if (!confirm(`Excluir a equipe "${team.name}"?`)) return;
                                        try {
                                          await teamsApi.delete(competition.id, team.id);
                                          await loadTeams();
                                        } catch {
                                          setTeamError("Erro ao excluir equipe.");
                                        }
                                      }}
                                    >
                                      Excluir
                                    </Button>
                                  )}
                                </div>
                              </td>
                            </tr>

                            {/* Inline member management */}
                            {isExpanded && (
                              <tr>
                                <td colSpan={4} className="px-4 py-3 bg-blue-50 border-t border-blue-100">
                                  <div className="space-y-3">
                                    <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                      Membros de {team.name}
                                    </p>

                                    {membersLoading ? (
                                      <p className="text-sm text-gray-400">Carregando membros...</p>
                                    ) : members.length === 0 ? (
                                      <p className="text-sm text-gray-400">Nenhum membro cadastrado.</p>
                                    ) : (
                                      <ul className="space-y-1">
                                        {members.map((mem) => (
                                          <li
                                            key={mem.id}
                                            className="flex items-center justify-between text-sm text-gray-700 bg-white rounded px-3 py-1.5 border border-gray-100"
                                          >
                                            <span>{mem.user_name}</span>
                                            {canManage && (
                                              <Button
                                                size="sm"
                                                variant="danger"
                                                onClick={() =>
                                                  handleRemoveMember(team.id, mem.user_id, mem.user_name)
                                                }
                                              >
                                                Remover
                                              </Button>
                                            )}
                                          </li>
                                        ))}
                                      </ul>
                                    )}

                                    {canManage && (
                                      <div className="flex items-center gap-2 pt-1">
                                        <select
                                          className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 flex-1 max-w-xs"
                                          value={addMemberUserId}
                                          onChange={(e) =>
                                            setAddMemberUserId(
                                              e.target.value === "" ? "" : Number(e.target.value)
                                            )
                                          }
                                        >
                                          <option value="">Selecionar usuário...</option>
                                          {availableUsers.map((u) => (
                                            <option key={u.id} value={u.id}>
                                              {u.full_name} ({u.email})
                                            </option>
                                          ))}
                                        </select>
                                        <Button
                                          size="sm"
                                          variant="primary"
                                          onClick={() => handleAddMember(team.id)}
                                          disabled={addMemberUserId === ""}
                                        >
                                          <PlusIcon className="h-4 w-4" />
                                          Adicionar Membro
                                        </Button>
                                      </div>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {canManage && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  Adicionar Equipe
                </h3>
                {teamError && (
                  <div className="mb-3">
                    <Alert variant="error">{teamError}</Alert>
                  </div>
                )}
                {teamSuccess && (
                  <div className="mb-3">
                    <Alert variant="success">{teamSuccess}</Alert>
                  </div>
                )}
                <form
                  onSubmit={handleAddTeam}
                  className="flex flex-wrap items-end gap-3"
                >
                  <div className="flex-1 min-w-[160px]">
                    <Input
                      label="Nome"
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      placeholder="Ex: Team Alpha"
                      required
                    />
                  </div>
                  <div className="min-w-[160px]">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Categoria
                    </label>
                    <select
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      value={newTeamCategoryId}
                      onChange={(e) =>
                        setNewTeamCategoryId(e.target.value === "" ? "" : Number(e.target.value))
                      }
                      required
                    >
                      <option value="">Selecione...</option>
                      {categories
                        .filter((c) => c.is_active && c.category_type === "team")
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                    </select>
                  </div>
                  <Button type="submit" size="sm" variant="primary" isLoading={teamSaving}>
                    <PlusIcon className="h-4 w-4" />
                    Adicionar
                  </Button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* --- Heats tab --- */}
        {activeTab === "heats" && (
          <div className="space-y-4">
            {heatTeamActionError && (
              <Alert variant="error">{heatTeamActionError}</Alert>
            )}
            {heatsLoading ? (
              <p className="text-sm text-gray-400">Carregando baterias...</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Nome
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Capacidade
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Timers / Equipes
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ações
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {heats.length === 0 ? (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-4 py-6 text-center text-gray-400 text-sm"
                        >
                          Nenhuma bateria cadastrada.
                        </td>
                      </tr>
                    ) : (
                      heats.map((heat) => {
                        const heatBadge = HEAT_STATUS_BADGE[heat.status] ?? HEAT_STATUS_BADGE.pending;
                        const isExpanded = expandedHeatId === heat.id;

                        // Teams not yet in this heat
                        const heatTeamIds = new Set((heat.teams ?? []).map((t: HeatTeamRef) => t.team_id));
                        const availableTeamsForHeat = teams.filter((t) => !heatTeamIds.has(t.id));

                        return (
                          <React.Fragment key={heat.id}>
                            <tr className="border-t border-gray-100 hover:bg-gray-50">
                              <td className="px-4 py-2 font-medium text-gray-900">
                                {heat.name}
                              </td>
                              <td className="px-4 py-2">
                                <Badge variant={heatBadge.variant}>{heatBadge.label}</Badge>
                              </td>
                              <td className="px-4 py-2 text-gray-600">
                                {heat.max_participants ?? "—"}
                              </td>
                              <td className="px-4 py-2 text-gray-600">
                                {heat.timer_count} / {heat.team_count}
                              </td>
                              <td className="px-4 py-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                  {canManage && (
                                    <Button
                                      size="sm"
                                      variant={isExpanded ? "primary" : "secondary"}
                                      onClick={() => handleToggleHeatTeams(heat.id)}
                                    >
                                      Equipes
                                      {isExpanded ? (
                                        <ChevronUpIcon className="h-3.5 w-3.5" />
                                      ) : (
                                        <ChevronDownIcon className="h-3.5 w-3.5" />
                                      )}
                                    </Button>
                                  )}
                                  {canManage &&
                                    competition.status === "active" &&
                                    heat.status !== "finished" && (
                                      <Button
                                        size="sm"
                                        variant="primary"
                                        onClick={() => handleStartHeat(heat.id, heat.name)}
                                      >
                                        Iniciar
                                      </Button>
                                    )}
                                  {canManage && (
                                    <Button
                                      size="sm"
                                      variant="danger"
                                      onClick={() => handleDeleteHeat(heat.id, heat.name)}
                                    >
                                      Excluir
                                    </Button>
                                  )}
                                </div>
                              </td>
                            </tr>

                            {/* Inline team association for heat */}
                            {isExpanded && (
                              <tr>
                                <td colSpan={5} className="px-4 py-3 bg-blue-50 border-t border-blue-100">
                                  <div className="space-y-3">
                                    <p className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                      Equipes na bateria: {heat.name}
                                    </p>

                                    {(heat.teams ?? []).length === 0 ? (
                                      <p className="text-sm text-gray-400">
                                        Nenhuma equipe nesta bateria.
                                      </p>
                                    ) : (
                                      <ul className="space-y-1">
                                        {(heat.teams ?? []).map((ht: HeatTeamRef) => (
                                          <li
                                            key={ht.team_id}
                                            className="flex items-center justify-between text-sm text-gray-700 bg-white rounded px-3 py-1.5 border border-gray-100"
                                          >
                                            <span>{ht.team_name}</span>
                                            {canManage && (
                                              <Button
                                                size="sm"
                                                variant="danger"
                                                onClick={() =>
                                                  handleRemoveTeamFromHeat(
                                                    heat.id,
                                                    ht.team_id,
                                                    ht.team_name
                                                  )
                                                }
                                              >
                                                Remover
                                              </Button>
                                            )}
                                          </li>
                                        ))}
                                      </ul>
                                    )}

                                    {canManage && availableTeamsForHeat.length > 0 && (
                                      <div className="flex items-center gap-2 pt-1">
                                        <select
                                          className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 flex-1 max-w-xs"
                                          value={addHeatTeamId}
                                          onChange={(e) =>
                                            setAddHeatTeamId(
                                              e.target.value === "" ? "" : Number(e.target.value)
                                            )
                                          }
                                        >
                                          <option value="">Selecionar equipe...</option>
                                          {availableTeamsForHeat.map((t) => (
                                            <option key={t.id} value={t.id}>
                                              {t.name}
                                            </option>
                                          ))}
                                        </select>
                                        <Button
                                          size="sm"
                                          variant="primary"
                                          onClick={() => handleAddTeamToHeat(heat.id)}
                                          disabled={addHeatTeamId === ""}
                                        >
                                          <PlusIcon className="h-4 w-4" />
                                          Adicionar Equipe
                                        </Button>
                                      </div>
                                    )}

                                    {canManage && availableTeamsForHeat.length === 0 && (
                                      <p className="text-sm text-gray-400 italic">
                                        Todas as equipes já estão nesta bateria.
                                      </p>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {canManage && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  Adicionar Bateria
                </h3>
                {heatError && (
                  <div className="mb-3">
                    <Alert variant="error">{heatError}</Alert>
                  </div>
                )}
                {heatSuccess && (
                  <div className="mb-3">
                    <Alert variant="success">{heatSuccess}</Alert>
                  </div>
                )}
                <form
                  onSubmit={handleAddHeat}
                  className="flex flex-wrap items-end gap-3"
                >
                  <div className="flex-1 min-w-[160px]">
                    <Input
                      label="Nome"
                      value={newHeatName}
                      onChange={(e) => setNewHeatName(e.target.value)}
                      placeholder="Ex: Bateria 1"
                      required
                    />
                  </div>
                  <div className="min-w-[120px]">
                    <Input
                      label="Máx. Participantes"
                      type="number"
                      min={1}
                      value={newHeatMaxParticipants}
                      onChange={(e) =>
                        setNewHeatMaxParticipants(
                          e.target.value === "" ? "" : Number(e.target.value)
                        )
                      }
                      placeholder="Opcional"
                    />
                  </div>
                  <Button type="submit" size="sm" variant="primary" isLoading={heatSaving}>
                    <PlusIcon className="h-4 w-4" />
                    Adicionar
                  </Button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* --- Invite tab --- */}
        {activeTab === "invite" && (
          <div className="bg-white rounded-lg border border-gray-200 p-4 max-w-lg space-y-4">
            <h3 className="text-sm font-semibold text-gray-700">Convidar Atleta</h3>
            {inviteError && <Alert variant="error">{inviteError}</Alert>}
            {inviteSuccess && <Alert variant="success">{inviteSuccess}</Alert>}
            <form onSubmit={handleSendInvite} className="space-y-3">
              <Input
                label="E-mail do Atleta *"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="atleta@example.com"
                required
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Categoria (opcional)
                </label>
                <select
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={inviteCategoryId}
                  onChange={(e) => {
                    setInviteCategoryId(e.target.value === "" ? "" : Number(e.target.value));
                    setInviteTeamId("");
                  }}
                >
                  <option value="">Sem categoria específica</option>
                  {categories
                    .filter((c) => c.is_active)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </div>

              {inviteCategoryId !== "" && (
                <div>
                  {inviteIsIndividualCategory ? (
                    <p className="text-xs text-blue-600 bg-blue-50 rounded px-3 py-2 border border-blue-100">
                      Para categoria individual, uma equipe será criada automaticamente com o e-mail do atleta.
                    </p>
                  ) : (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Equipe (opcional)
                      </label>
                      <select
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                        value={inviteTeamId}
                        onChange={(e) =>
                          setInviteTeamId(e.target.value === "" ? "" : Number(e.target.value))
                        }
                      >
                        <option value="">Sem equipe específica</option>
                        {teamsForInviteCategory.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end pt-1">
                <Button type="submit" variant="primary" isLoading={inviteSaving}>
                  Enviar Convite
                </Button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------
export default function CompetitionsPage() {
  const { user } = useAuthStore();
  const canManage = user?.role === "admin" || user?.role === "operator";
  const isAdmin = user?.role === "admin";

  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [modalities, setModalities] = useState<Modality[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CompetitionCreate>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // HH:MM:SS display state for the duration field in the create form
  // (Driven by form.duration_seconds; HmsDurationInput handles its own local state via useEffect)

  // Date input display (Brazilian format dd/mm/aaaa)
  const [eventDateDisplay, setEventDateDisplay] = useState("");

  // Which competition's panel is open (by id), null = none
  const [openPanelId, setOpenPanelId] = useState<number | null>(null);

  // Edit form state
  const [editingCompId, setEditingCompId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<CompetitionCreate>(INITIAL_FORM);
  const [editDateDisplay, setEditDateDisplay] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Per-row action loading states
  const [cloningId, setCloningId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; msg: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [{ data }, modData] = await Promise.all([
        competitionsApi.list(),
        modalitiesApi.list(),
      ]);
      setCompetitions(data);
      setModalities(modData);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await competitionsApi.create(form);
      setShowForm(false);
      setForm(INITIAL_FORM);
      setEventDateDisplay("");
      await load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail) && detail.length > 0) {
        setError(String((detail[0] as { msg?: string })?.msg ?? "Erro ao criar competição. Tente novamente."));
      } else {
        setError("Erro ao criar competição. Tente novamente.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleClone(id: number) {
    setRowError(null);
    setCloningId(id);
    try {
      await competitionsApi.clone(id);
      await load();
    } catch {
      setRowError({ id, msg: "Erro ao clonar competição." });
    } finally {
      setCloningId(null);
    }
  }

  async function handleDelete(id: number, name: string) {
    if (!confirm(`Excluir a competição "${name}"? Esta ação não pode ser desfeita.`)) return;
    setRowError(null);
    setDeletingId(id);
    try {
      await competitionsApi.delete(id);
      if (openPanelId === id) setOpenPanelId(null);
      await load();
    } catch {
      setRowError({ id, msg: "Erro ao excluir competição." });
    } finally {
      setDeletingId(null);
    }
  }

  function openEditForm(comp: Competition) {
    setEditingCompId(comp.id);
    setEditForm({
      name: comp.name,
      location: comp.location ?? "",
      event_date: comp.event_date ?? "",
      modality_id: comp.modality_id ?? undefined,
      duration_seconds: comp.duration_seconds ?? undefined,
      max_athletes: comp.max_athletes,
      rules: comp.rules ?? "",
    });
    setEditDateDisplay(comp.event_date ? isoToPtDate(comp.event_date) : "");
    setEditError(null);
    setOpenPanelId(null); // close management panel
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editingCompId) return;
    setEditError(null);
    setEditSaving(true);
    try {
      await competitionsApi.update(editingCompId, {
        name: editForm.name,
        location: editForm.location || undefined,
        event_date: editForm.event_date || undefined,
        modality_id: editForm.modality_id,
        duration_seconds: editForm.duration_seconds,
        max_athletes: editForm.max_athletes,
        rules: editForm.rules || undefined,
      });
      setEditingCompId(null);
      await load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (typeof detail === "string") {
        setEditError(detail);
      } else if (Array.isArray(detail) && detail.length > 0) {
        setEditError(String((detail[0] as { msg?: string })?.msg ?? "Erro ao salvar competição."));
      } else {
        setEditError("Erro ao salvar competição. Tente novamente.");
      }
    } finally {
      setEditSaving(false);
    }
  }

  function togglePanel(id: number) {
    setOpenPanelId((prev) => (prev === id ? null : id));
    if (editingCompId) setEditingCompId(null);
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Competições</h1>
          <p className="text-gray-500 text-sm mt-1">
            Gerencie as competições do sistema
          </p>
        </div>
        {canManage && (
          <Button variant="primary" onClick={() => setShowForm(!showForm)}>
            <PlusIcon className="h-4 w-4" />
            Nova Competição
          </Button>
        )}
      </div>

      {/* Create form */}
      {showForm && canManage && (
        <Card>
          <CardHeader title="Nova Competição" />
          {error && (
            <div className="mb-4">
              <Alert variant="error">{error}</Alert>
            </div>
          )}
          <form
            onSubmit={handleCreate}
            className="grid grid-cols-1 gap-4 sm:grid-cols-2"
          >
            <div className="sm:col-span-2">
              <Input
                label="Nome *"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Hyrox São Paulo 2026"
                required
              />
            </div>
            <Input
              label="Local"
              value={form.location ?? ""}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="Ex: São Paulo, SP"
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Modalidade
              </label>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={form.modality_id ?? ""}
                onChange={(e) => {
                  const selectedId = e.target.value === "" ? undefined : Number(e.target.value);
                  const selectedModality = modalities.find((m) => m.id === selectedId);
                  setForm({
                    ...form,
                    modality_id: selectedId,
                    duration_seconds:
                      form.duration_seconds === undefined &&
                      selectedModality?.default_duration_seconds != null
                        ? selectedModality.default_duration_seconds
                        : form.duration_seconds,
                  });
                }}
              >
                <option value="">Selecione...</option>
                {modalities.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Date: Brazilian format */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Data do Evento
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="dd/mm/aaaa"
                value={eventDateDisplay || (form.event_date ? isoToPtDate(form.event_date) : "")}
                onChange={(e) => {
                  // Auto-mascara: strip non-digits, re-insere "/" nas posições certas
                  let digits = e.target.value.replace(/\D/g, "").slice(0, 8);
                  let masked = digits;
                  if (digits.length > 4) {
                    masked = digits.slice(0, 2) + "/" + digits.slice(2, 4) + "/" + digits.slice(4);
                  } else if (digits.length > 2) {
                    masked = digits.slice(0, 2) + "/" + digits.slice(2);
                  }
                  setEventDateDisplay(masked);
                  const iso = ptDateToIso(masked);
                  setForm({ ...form, event_date: iso !== masked ? iso : masked });
                }}
                maxLength={10}
              />
            </div>

            {/* Duration: HH:MM:SS */}
            <div>
              <HmsDurationInput
                label="Duração (HH:MM:SS)"
                valueSeconds={form.duration_seconds}
                onChange={(seconds) =>
                  setForm({ ...form, duration_seconds: seconds })
                }
              />
            </div>

            <Input
              label="Máx. Atletas"
              type="number"
              min={1}
              max={300}
              value={form.max_athletes ?? 300}
              onChange={(e) =>
                setForm({ ...form, max_athletes: Number(e.target.value) })
              }
            />
            <div className="sm:col-span-2 flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowForm(false);
                  setError(null);
                  setForm(INITIAL_FORM);
                  setEventDateDisplay("");
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" isLoading={saving}>
                Criar Competição
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Competitions list */}
      <Card padding="none">
        <CardHeader
          title="Lista de Competições"
          description={`${competitions.length} competição(ões) cadastrada(s)`}
          className="px-6 pt-6"
        />
        {loading ? (
          <div className="px-6 pb-8 text-center text-gray-400 text-sm">
            Carregando...
          </div>
        ) : competitions.length === 0 ? (
          <div className="px-6 pb-12 text-center text-gray-400 text-sm">
            Nenhuma competição cadastrada ainda.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-gray-100 bg-gray-50">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Nome
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Local
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Modalidade
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Data
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duração
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Atletas
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody>
                {competitions.map((comp) => {
                  const { label, variant } =
                    STATUS_BADGE[comp.status] ?? STATUS_BADGE.draft;
                  const isPanelOpen = openPanelId === comp.id;

                  return (
                    <React.Fragment key={comp.id}>
                      <tr
                        className={[
                          "hover:bg-gray-50 transition-colors",
                          isPanelOpen ? "bg-primary-50" : "",
                        ].join(" ")}
                      >
                        <td className="px-6 py-4 font-medium text-gray-900">
                          {comp.name}
                        </td>
                        <td className="px-6 py-4 text-gray-500">
                          {comp.location ?? "—"}
                        </td>
                        <td className="px-6 py-4 text-gray-500">
                          {comp.modality_name ?? "—"}
                        </td>
                        <td className="px-6 py-4 text-gray-500">
                          {formatDate(comp.event_date)}
                        </td>
                        <td className="px-6 py-4 text-gray-500">
                          {formatHms(comp.duration_seconds)}
                        </td>
                        <td className="px-6 py-4 text-gray-500">
                          {comp.max_athletes}
                        </td>
                        <td className="px-6 py-4">
                          <Badge variant={variant}>{label}</Badge>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2 flex-wrap">
                            {canManage && (
                              <Button
                                size="sm"
                                variant={isPanelOpen ? "primary" : "secondary"}
                                onClick={() => togglePanel(comp.id)}
                              >
                                Gerenciar
                                {isPanelOpen ? (
                                  <ChevronUpIcon className="h-3.5 w-3.5" />
                                ) : (
                                  <ChevronDownIcon className="h-3.5 w-3.5" />
                                )}
                              </Button>
                            )}
                            {canManage && comp.status === "draft" && (
                              <Button
                                size="sm"
                                variant={editingCompId === comp.id ? "primary" : "ghost"}
                                onClick={() => {
                                  if (editingCompId === comp.id) setEditingCompId(null);
                                  else openEditForm(comp);
                                }}
                              >
                                Editar
                              </Button>
                            )}
                            {canManage && (
                              <Button
                                size="sm"
                                variant="ghost"
                                isLoading={cloningId === comp.id}
                                onClick={() => handleClone(comp.id)}
                              >
                                Clonar
                              </Button>
                            )}
                            {isAdmin && (
                              <Button
                                size="sm"
                                variant="danger"
                                isLoading={deletingId === comp.id}
                                onClick={() => handleDelete(comp.id, comp.name)}
                              >
                                Excluir
                              </Button>
                            )}
                            {!canManage && (
                              <Link
                                to={`/ranking/${comp.id}`}
                                className="text-primary-600 hover:text-primary-700 font-medium text-sm"
                              >
                                Ranking
                              </Link>
                            )}
                          </div>
                          {rowError?.id === comp.id && (
                            <p className="mt-1 text-xs text-red-600">{rowError.msg}</p>
                          )}
                        </td>
                      </tr>

                      {/* Inline management panel */}
                      {isPanelOpen && (
                        <tr>
                          <td colSpan={8} className="p-0">
                            <ManagementPanel
                              competition={comp}
                              canManage={canManage}
                              isAdmin={isAdmin}
                              onStatusChanged={load}
                            />
                          </td>
                        </tr>
                      )}

                      {/* Inline edit form (only for draft competitions) */}
                      {editingCompId === comp.id && comp.status === "draft" && (
                        <tr>
                          <td colSpan={8} className="p-0">
                            <div className="bg-blue-50 dark:bg-blue-900/20 border-t border-blue-200 dark:border-blue-800 p-4">
                              <p className="text-sm font-semibold text-blue-800 dark:text-blue-200 mb-3">Editar Competição</p>
                              {editError && (
                                <div className="mb-3 px-3 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-400">
                                  {editError}
                                </div>
                              )}
                              <form onSubmit={handleEditSave} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div className="sm:col-span-2 lg:col-span-3">
                                  <label className="block text-xs font-medium text-gray-700 mb-1">Nome *</label>
                                  <input
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    value={editForm.name}
                                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                    required
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 mb-1">Local</label>
                                  <input
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    value={editForm.location ?? ""}
                                    onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                                    placeholder="Ex: São Paulo, SP"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 mb-1">Modalidade</label>
                                  <select
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    value={editForm.modality_id ?? ""}
                                    onChange={(e) => {
                                      const selectedId = e.target.value === "" ? undefined : Number(e.target.value);
                                      const selectedModality = modalities.find((m) => m.id === selectedId);
                                      setEditForm({
                                        ...editForm,
                                        modality_id: selectedId,
                                        duration_seconds:
                                          editForm.duration_seconds === undefined && selectedModality?.default_duration_seconds != null
                                            ? selectedModality.default_duration_seconds
                                            : editForm.duration_seconds,
                                      });
                                    }}
                                  >
                                    <option value="">Selecione...</option>
                                    {modalities.map((m) => (
                                      <option key={m.id} value={m.id}>{m.name}</option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 mb-1">Data do Evento</label>
                                  <input
                                    type="text"
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    placeholder="dd/mm/aaaa"
                                    value={editDateDisplay || (editForm.event_date ? isoToPtDate(editForm.event_date) : "")}
                                    onChange={(e) => {
                                      let digits = e.target.value.replace(/\D/g, "").slice(0, 8);
                                      let masked = digits;
                                      if (digits.length > 4) {
                                        masked = digits.slice(0, 2) + "/" + digits.slice(2, 4) + "/" + digits.slice(4);
                                      } else if (digits.length > 2) {
                                        masked = digits.slice(0, 2) + "/" + digits.slice(2);
                                      }
                                      setEditDateDisplay(masked);
                                      const iso = ptDateToIso(masked);
                                      setEditForm({ ...editForm, event_date: iso !== masked ? iso : masked });
                                    }}
                                    maxLength={10}
                                  />
                                </div>
                                <div>
                                  <HmsDurationInput
                                    label="Duração (HH:MM:SS)"
                                    valueSeconds={editForm.duration_seconds}
                                    onChange={(seconds) => setEditForm({ ...editForm, duration_seconds: seconds })}
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 mb-1">Máx. Atletas</label>
                                  <input
                                    type="number"
                                    min={1}
                                    max={300}
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    value={editForm.max_athletes ?? 300}
                                    onChange={(e) => setEditForm({ ...editForm, max_athletes: Number(e.target.value) })}
                                  />
                                </div>
                                <div className="sm:col-span-2 lg:col-span-3 flex justify-end gap-3 pt-1">
                                  <Button
                                    type="button"
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => setEditingCompId(null)}
                                    disabled={editSaving}
                                  >
                                    Cancelar
                                  </Button>
                                  <Button type="submit" variant="primary" size="sm" isLoading={editSaving}>
                                    Salvar Alterações
                                  </Button>
                                </div>
                              </form>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

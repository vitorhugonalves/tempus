import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  PlusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from "@heroicons/react/24/outline";
import { competitionsApi, type CompetitionCreate } from "../api/competitions";
import { categoriesApi } from "../api/categories";
import { penaltyTypesApi } from "../api/timers";
import { authApi } from "../api/auth";
import { useAuthStore } from "../store/auth";
import { Card, CardHeader } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type { Category, Competition, PenaltyType } from "../types";

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

const INITIAL_FORM: CompetitionCreate = {
  name: "",
  location: "",
  event_date: "",
  modality: "",
  max_athletes: 300,
};

// ---------------------------------------------------------------------------
// Helper: format ISO date as dd/mm/yyyy
// ---------------------------------------------------------------------------
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR");
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

type PanelTab = "categories" | "penalties" | "invite";

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
  const [inviteSaving, setInviteSaving] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

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

  useEffect(() => {
    loadCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competition.id]);

  useEffect(() => {
    if (activeTab === "penalties" && penalties.length === 0 && !penLoading) {
      loadPenalties();
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
    } catch {
      setCatError("Erro ao criar categoria.");
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
    } catch {
      setPenError("Erro ao criar tipo de penalidade.");
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
        inviteCategoryId !== "" ? Number(inviteCategoryId) : undefined
      );
      setInviteEmail("");
      setInviteCategoryId("");
      setInviteSuccess("Convite enviado com sucesso.");
    } catch {
      setInviteError("Erro ao enviar convite. Verifique o e-mail e tente novamente.");
    } finally {
      setInviteSaving(false);
    }
  }

  const tabClass = (tab: PanelTab) =>
    [
      "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
      activeTab === tab
        ? "border-primary-600 text-primary-600"
        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
    ].join(" ");

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
        <div className="flex border-b border-gray-200 mb-4">
          <button className={tabClass("categories")} onClick={() => setActiveTab("categories")}>
            Categorias
          </button>
          <button className={tabClass("penalties")} onClick={() => setActiveTab("penalties")}>
            Tipos de Penalidade
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
                  onChange={(e) =>
                    setInviteCategoryId(e.target.value === "" ? "" : Number(e.target.value))
                  }
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
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CompetitionCreate>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Which competition's panel is open (by id), null = none
  const [openPanelId, setOpenPanelId] = useState<number | null>(null);

  // Per-row action loading states
  const [cloningId, setCloningId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; msg: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const { data } = await competitionsApi.list();
      setCompetitions(data);
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
      await load();
    } catch {
      setError("Erro ao criar competição. Tente novamente.");
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

  function togglePanel(id: number) {
    setOpenPanelId((prev) => (prev === id ? null : id));
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
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="Ex: São Paulo, SP"
            />
            <Input
              label="Modalidade"
              value={form.modality}
              onChange={(e) => setForm({ ...form, modality: e.target.value })}
              placeholder="Ex: Hyrox, CrossFit"
            />
            <Input
              label="Data do Evento"
              type="date"
              value={form.event_date}
              onChange={(e) => setForm({ ...form, event_date: e.target.value })}
            />
            <Input
              label="Máx. Atletas"
              type="number"
              min={1}
              max={300}
              value={form.max_athletes}
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
                    <>
                      <tr
                        key={comp.id}
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
                          {comp.modality ?? "—"}
                        </td>
                        <td className="px-6 py-4 text-gray-500">
                          {formatDate(comp.event_date)}
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
                        <tr key={`${comp.id}-panel`}>
                          <td colSpan={7} className="p-0">
                            <ManagementPanel
                              competition={comp}
                              canManage={canManage}
                              isAdmin={isAdmin}
                              onStatusChanged={load}
                            />
                          </td>
                        </tr>
                      )}
                    </>
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

import { useEffect, useRef, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { PlusIcon, ArrowUpTrayIcon, PencilIcon, ChevronDownIcon, ChevronUpIcon } from "@heroicons/react/24/outline";
import { teamsApi, type TeamCreate } from "../../api/teams";
import { athletesApi } from "../../api/athletes";
import { categoriesApi } from "../../api/categories";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Athlete, Category, Competition, Team, TeamBulkResult } from "../../types";

interface OutletCtx {
  competition: Competition;
}

export default function TeamsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  useOutletContext<OutletCtx>();
  const id = Number(competitionId);
  const fileRef = useRef<HTMLInputElement>(null);

  const [teams, setTeams] = useState<Team[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [allAthletes, setAllAthletes] = useState<Athlete[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [filterCat, setFilterCat] = useState<string>("");
  const [search, setSearch] = useState("");

  const [form, setForm] = useState<{ name: string; category_id?: number }>({
    name: "",
    category_id: undefined,
  });

  // Edit state
  const [editingTeamId, setEditingTeamId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");

  // Athletes panel state
  const [expandedTeamId, setExpandedTeamId] = useState<number | null>(null);
  const [selectedAthlete, setSelectedAthlete] = useState<string>("");

  useEffect(() => {
    Promise.all([
      teamsApi.list(id),
      categoriesApi.list(id),
      athletesApi.list(id).then((r: any) => r.data ?? r),
    ])
      .then(([t, c, a]) => { setTeams(t); setCategories(c); setAllAthletes(a); })
      .catch(() => setError("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  }, [id]);

  const filtered = teams.filter((t) => {
    if (filterCat && String(t.category_id) !== filterCat) return false;
    if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload: TeamCreate = {
        name: form.name,
        category_id: form.category_id ?? 0,
      };
      const team = await teamsApi.create(id, payload);
      setTeams((p) => [...p, team]);
      setForm({ name: "", category_id: undefined });
      setShowForm(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao criar equipe");
    }
  }

  async function handleDelete(teamId: number) {
    if (!window.confirm("Remover esta equipe?")) return;
    try {
      await teamsApi.delete(id, teamId);
      setTeams((p) => p.filter((t) => t.id !== teamId));
      setAllAthletes((p) => p.map((a) => a.team_id === teamId ? { ...a, team_id: null, team_name: null } : a));
    } catch {
      setError("Erro ao remover equipe");
    }
  }

  function startEdit(team: Team) {
    setEditingTeamId(team.id);
    setEditingName(team.name);
  }

  async function handleSaveEdit(teamId: number) {
    if (!editingName.trim()) return;
    setError(null);
    try {
      const updated = await teamsApi.update(id, teamId, { name: editingName.trim() });
      setTeams((p) => p.map((t) => t.id === teamId ? updated : t));
      setEditingTeamId(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao salvar equipe");
    }
  }

  function toggleExpanded(teamId: number) {
    setExpandedTeamId((prev) => prev === teamId ? null : teamId);
    setSelectedAthlete("");
  }

  async function handleRemoveAthlete(athlete: Athlete) {
    try {
      await athletesApi.update(id, athlete.id, { team_id: null } as any);
      setAllAthletes((p) =>
        p.map((a) => a.id === athlete.id ? { ...a, team_id: null, team_name: null } : a)
      );
    } catch {
      setError("Erro ao remover atleta da equipe");
    }
  }

  async function handleAddAthlete(teamId: number, teamName: string) {
    const athleteId = Number(selectedAthlete);
    if (!athleteId) return;
    try {
      await athletesApi.update(id, athleteId, { team_id: teamId } as any);
      setAllAthletes((p) =>
        p.map((a) => a.id === athleteId ? { ...a, team_id: teamId, team_name: teamName } : a)
      );
      setSelectedAthlete("");
    } catch {
      setError("Erro ao adicionar atleta à equipe");
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setImportResult(null);
    try {
      const data: TeamBulkResult = await teamsApi.importCsv(id, file);
      setImportResult(
        `${data.created} equipe(s) importada(s) com sucesso.${
          data.errors.length ? ` ${data.errors.length} erro(s).` : ""
        }`
      );
      const updated = await teamsApi.list(id);
      setTeams(updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro na importação");
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Equipes</h1>
        <div className="flex items-start gap-3">
          <div className="flex flex-col items-end gap-1">
            <label className="flex cursor-pointer items-center gap-2 rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
              <ArrowUpTrayIcon className="h-4 w-4" />
              Importar CSV
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="sr-only"
                onChange={handleImport}
              />
            </label>
            <p className="text-xs text-gray-400">
              Formato: <code className="font-mono">nome_equipe;categoria</code>
            </p>
          </div>
          <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
            <PlusIcon className="h-4 w-4" /> Nova Equipe
          </Button>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {importResult && <Alert variant="success">{importResult}</Alert>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
        >
          <h3 className="font-medium">Nova Equipe</h3>
          <Input
            label="Nome *"
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            required
          />
          <div>
            <label className="block text-sm font-medium text-gray-700">Categoria</label>
            <select
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              value={form.category_id ?? ""}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  category_id: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            >
              <option value="">Sem categoria</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Salvar</Button>
            <Button variant="secondary" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {/* Filtros */}
      <div className="flex gap-3">
        <Input
          placeholder="Buscar por nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          className="rounded-md border-gray-300 text-sm shadow-sm"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categories.map((c) => (
            <option key={c.id} value={String(c.id)}>{c.name}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Nome</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Categoria</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Atletas</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase text-gray-500">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">
                  Nenhuma equipe encontrada
                </td>
              </tr>
            ) : (
              filtered.map((team) => {
                const cat = categories.find((c) => c.id === team.category_id);
                const teamAthletes = allAthletes.filter((a) => a.team_id === team.id);
                const unassigned = allAthletes.filter((a) => !a.team_id);
                const isExpanded = expandedTeamId === team.id;
                const isEditing = editingTeamId === team.id;

                return (
                  <>
                    <tr key={team.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-medium text-gray-900">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              className="rounded border border-gray-300 px-2 py-1 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                              value={editingName}
                              onChange={(e) => setEditingName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleSaveEdit(team.id);
                                if (e.key === "Escape") setEditingTeamId(null);
                              }}
                              autoFocus
                            />
                            <button
                              onClick={() => handleSaveEdit(team.id)}
                              className="text-xs font-medium text-primary-600 hover:text-primary-800"
                            >
                              Salvar
                            </button>
                            <button
                              onClick={() => setEditingTeamId(null)}
                              className="text-xs font-medium text-gray-500 hover:text-gray-700"
                            >
                              Cancelar
                            </button>
                          </div>
                        ) : (
                          team.name
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{cat?.name ?? "—"}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{teamAthletes.length}</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <button
                            onClick={() => toggleExpanded(team.id)}
                            className="text-sm font-medium text-gray-600 hover:text-gray-800 flex items-center gap-1"
                          >
                            {isExpanded ? (
                              <ChevronUpIcon className="h-4 w-4" />
                            ) : (
                              <ChevronDownIcon className="h-4 w-4" />
                            )}
                            Atletas
                          </button>
                          <button
                            onClick={() => startEdit(team)}
                            className="text-sm font-medium text-primary-600 hover:text-primary-800 flex items-center gap-1"
                          >
                            <PencilIcon className="h-4 w-4" />
                            Editar
                          </button>
                          <button
                            onClick={() => handleDelete(team.id)}
                            className="text-sm font-medium text-red-600 hover:text-red-800"
                          >
                            Remover
                          </button>
                        </div>
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr key={`${team.id}-athletes`}>
                        <td colSpan={4} className="bg-gray-50 px-6 py-4">
                          <div className="space-y-3">
                            <p className="text-xs font-semibold uppercase text-gray-500">
                              Atletas — {team.name}
                            </p>

                            {teamAthletes.length === 0 ? (
                              <p className="text-sm text-gray-400">Nenhum atleta nesta equipe.</p>
                            ) : (
                              <div className="flex flex-wrap gap-2">
                                {teamAthletes.map((a) => (
                                  <span
                                    key={a.id}
                                    className="flex items-center gap-1 rounded-full bg-white px-3 py-1 text-sm shadow-sm border border-gray-200"
                                  >
                                    {a.name}
                                    <button
                                      onClick={() => handleRemoveAthlete(a)}
                                      className="ml-1 text-gray-400 hover:text-red-600 font-bold leading-none"
                                    >
                                      ×
                                    </button>
                                  </span>
                                ))}
                              </div>
                            )}

                            {unassigned.length > 0 && (
                              <div className="flex items-center gap-2 pt-1">
                                <select
                                  className="rounded-md border-gray-300 text-sm shadow-sm"
                                  value={selectedAthlete}
                                  onChange={(e) => setSelectedAthlete(e.target.value)}
                                >
                                  <option value="">Adicionar atleta...</option>
                                  {unassigned.map((a) => (
                                    <option key={a.id} value={a.id}>{a.name}</option>
                                  ))}
                                </select>
                                <button
                                  onClick={() => handleAddAthlete(team.id, team.name)}
                                  disabled={!selectedAthlete}
                                  className="rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40"
                                >
                                  Adicionar
                                </button>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { heatsApi, type HeatCreate } from "../../api/heats";
import { teamsApi } from "../../api/teams";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import Badge from "../../components/ui/Badge";
import type { Competition, Heat, Team } from "../../types";

interface OutletCtx {
  competition: Competition;
}

const HEAT_STATUS_BADGE: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  pending: { label: "Aguardando", variant: "gray" },
  running: { label: "Em andamento", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

export default function HeatsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  useOutletContext<OutletCtx>();
  const id = Number(competitionId);

  const [heats, setHeats] = useState<Heat[]>([]);
  const [allTeams, setAllTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newHeatName, setNewHeatName] = useState("");
  const [expandedHeatId, setExpandedHeatId] = useState<number | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<Record<number, string>>({});

  useEffect(() => {
    Promise.all([heatsApi.list(id), teamsApi.list(id)])
      .then(([h, t]) => {
        setHeats(h);
        setAllTeams(t);
      })
      .catch(() => setError("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload: HeatCreate = { name: newHeatName };
      const heat = await heatsApi.create(id, payload);
      setHeats((p) => [...p, heat]);
      setNewHeatName("");
      setShowForm(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao criar bateria");
    }
  }

  async function handleDelete(heatId: number) {
    if (!window.confirm("Remover esta bateria?")) return;
    try {
      await heatsApi.delete(id, heatId);
      setHeats((p) => p.filter((h) => h.id !== heatId));
    } catch {
      setError("Erro ao remover bateria");
    }
  }

  async function handleStart(heatId: number) {
    setError(null);
    try {
      const updated = await heatsApi.start(id, heatId);
      setHeats((p) => p.map((h) => (h.id === heatId ? updated : h)));
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao iniciar bateria");
    }
  }

  async function handleFinish(heatId: number) {
    if (!window.confirm("Encerrar esta bateria?")) return;
    setError(null);
    try {
      const updated = await heatsApi.finish(id, heatId);
      setHeats((p) => p.map((h) => (h.id === heatId ? updated : h)));
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao encerrar bateria");
    }
  }

  async function handleAddTeam(heatId: number) {
    const teamId = Number(selectedTeam[heatId]);
    if (!teamId) return;
    setError(null);
    try {
      const updated = await heatsApi.addTeam(id, heatId, teamId);
      setHeats((p) => p.map((h) => (h.id === heatId ? updated : h)));
      setSelectedTeam((p) => ({ ...p, [heatId]: "" }));
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao adicionar equipe");
    }
  }

  async function handleRemoveTeam(heatId: number, teamId: number) {
    setError(null);
    try {
      await heatsApi.removeTeam(id, heatId, teamId);
      setHeats((p) =>
        p.map((h) =>
          h.id === heatId
            ? { ...h, teams: h.teams.filter((t) => t.team_id !== teamId), team_count: h.team_count - 1 }
            : h
        )
      );
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao remover equipe");
    }
  }

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Baterias</h1>
        <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
          <PlusIcon className="h-4 w-4" /> Nova Bateria
        </Button>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="flex gap-3 rounded-lg border border-gray-200 bg-white p-4"
        >
          <Input
            label="Nome da bateria *"
            value={newHeatName}
            onChange={(e) => setNewHeatName(e.target.value)}
            required
            className="flex-1"
          />
          <div className="flex items-end gap-2">
            <Button type="submit">Criar</Button>
            <Button variant="secondary" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {heats.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">Nenhuma bateria cadastrada.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {heats.map((heat) => {
            const statusInfo = HEAT_STATUS_BADGE[heat.status] ?? { label: heat.status, variant: "gray" as const };
            const isExpanded = expandedHeatId === heat.id;
            const availableTeams = allTeams.filter(
              (t) => !heat.teams.some((ht) => ht.team_id === t.id)
            );
            return (
              <div key={heat.id} className="rounded-lg border border-gray-200 bg-white p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-gray-900">{heat.name}</p>
                    <p className="text-xs text-gray-500">
                      {heat.team_count} equipe(s) · {heat.timer_count} timer(s)
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                    {heat.status === "pending" && (
                      <button
                        onClick={() =>
                          setExpandedHeatId((prev) => (prev === heat.id ? null : heat.id))
                        }
                        className="text-sm font-medium text-primary-600 hover:text-primary-800"
                      >
                        {isExpanded ? "Fechar" : "Gerenciar Equipes"}
                      </button>
                    )}
                    {heat.status === "pending" && (
                      <Button onClick={() => handleStart(heat.id)} className="text-sm">
                        ▶ Iniciar
                      </Button>
                    )}
                    {heat.status === "running" && (
                      <button
                        onClick={() => handleFinish(heat.id)}
                        className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800"
                      >
                        ■ Encerrar
                      </button>
                    )}
                    {heat.status === "pending" && (
                      <button
                        onClick={() => handleDelete(heat.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Remover
                      </button>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
                    <p className="text-xs font-medium uppercase text-gray-500">
                      Equipes na bateria
                    </p>
                    {heat.teams.length === 0 ? (
                      <p className="text-sm text-gray-400">Nenhuma equipe vinculada.</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {heat.teams.map((ht) => (
                          <span
                            key={ht.team_id}
                            className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-3 py-1 text-sm font-medium text-primary-700"
                          >
                            {ht.team_name}
                            <button
                              onClick={() => handleRemoveTeam(heat.id, ht.team_id)}
                              className="ml-1 text-primary-400 hover:text-red-500"
                              title="Remover equipe da bateria"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2 items-center pt-1">
                      <select
                        className="flex-1 rounded-md border-gray-300 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        value={selectedTeam[heat.id] ?? ""}
                        onChange={(e) =>
                          setSelectedTeam((p) => ({ ...p, [heat.id]: e.target.value }))
                        }
                      >
                        <option value="">Selecione uma equipe...</option>
                        {availableTeams.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                      <Button
                        onClick={() => handleAddTeam(heat.id)}
                        disabled={!selectedTeam[heat.id]}
                        className="text-sm"
                      >
                        Adicionar
                      </Button>
                    </div>
                    {availableTeams.length === 0 && (
                      <p className="text-xs text-gray-400">
                        Todas as equipes já estão nesta bateria.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

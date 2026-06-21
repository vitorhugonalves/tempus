import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { wodResultsApi, type WodResultUpsert } from "../../api/wod_results";
import Alert from "../../components/ui/Alert";
import type { Competition, WodResult, WodResultsData } from "../../types";
import { useAuthStore } from "../../store/auth";

interface OutletCtx {
  competition: Competition;
}

function formatTime(seconds: number | null): string {
  if (seconds === null) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function parseTimeInput(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const match = trimmed.match(/^(\d+):([0-5]\d)$/);
  if (!match) return null;
  return parseInt(match[1]) * 60 + parseInt(match[2]);
}

interface EditingCell {
  teamId: number;
  wodId: number;
  existingId?: number;
}

export default function ResultsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  useOutletContext<OutletCtx>();
  const id = Number(competitionId);
  const { user } = useAuthStore();
  const canEdit = user?.role === "operator" || user?.role === "admin";

  const [data, setData] = useState<WodResultsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditingCell | null>(null);
  const [editTime, setEditTime] = useState("");
  const [editReps, setEditReps] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadData() {
    try {
      const d = await wodResultsApi.getData(id);
      setData(d);
    } catch {
      setError("Erro ao carregar resultados");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [id]);

  function getResult(teamId: number, wodId: number): WodResult | undefined {
    return data?.results.find((r) => r.team_id === teamId && r.wod_id === wodId);
  }

  function openEdit(teamId: number, wodId: number) {
    if (!canEdit) return;
    const existing = getResult(teamId, wodId);
    setEditing({ teamId, wodId, existingId: existing?.id });
    setEditTime(existing ? formatTime(existing.time_seconds) : "");
    setEditReps(existing?.reps != null ? String(existing.reps) : "");
  }

  function closeEdit() {
    setEditing(null);
    setEditTime("");
    setEditReps("");
  }

  async function handleSave() {
    if (!editing) return;
    const time_seconds = parseTimeInput(editTime);
    const reps = editReps.trim() ? parseInt(editReps) : null;
    if (time_seconds === null && reps === null) {
      setError("Informe pelo menos o tempo ou as repetições");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: WodResultUpsert = {
        wod_id: editing.wodId,
        team_id: editing.teamId,
        time_seconds,
        reps,
      };
      await wodResultsApi.upsert(id, payload);
      await loadData();
      closeEdit();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Erro ao salvar resultado");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!editing?.existingId) return;
    setSaving(true);
    setError(null);
    try {
      await wodResultsApi.delete(id, editing.existingId);
      await loadData();
      closeEdit();
    } catch {
      setError("Erro ao remover resultado");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!data) return null;

  if (data.wods.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Resultados</h1>
        <p className="text-sm text-gray-500">
          Nenhum WOD cadastrado. Adicione WODs na etapa de configuração da competição.
        </p>
      </div>
    );
  }

  if (data.teams.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Resultados</h1>
        <p className="text-sm text-gray-500">Nenhuma equipe cadastrada.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Resultados</h1>
        {canEdit && (
          <p className="text-sm text-gray-400">Clique em uma célula para inserir resultado</p>
        )}
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 w-40">
                Equipe
              </th>
              {data.wods.map((wod) => (
                <th
                  key={wod.id}
                  className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-500"
                >
                  <div>{wod.name}</div>
                  <div className="text-gray-400 normal-case font-normal">
                    {wod.wod_type === "for_time"
                      ? "Tempo"
                      : wod.wod_type === "amrap"
                      ? "AMRAP"
                      : wod.wod_type === "emom"
                      ? "EMOM"
                      : "Carga"}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {data.teams.map((team) => (
              <tr key={team.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">{team.name}</td>
                {data.wods.map((wod) => {
                  const result = getResult(team.id, wod.id);
                  const isEditing =
                    editing?.teamId === team.id && editing?.wodId === wod.id;

                  if (isEditing) {
                    return (
                      <td key={wod.id} className="px-2 py-2">
                        <div className="space-y-1 min-w-[160px]">
                          <input
                            type="text"
                            placeholder="mm:ss"
                            value={editTime}
                            onChange={(e) => setEditTime(e.target.value)}
                            className="block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-primary-500 focus:outline-none"
                          />
                          <input
                            type="number"
                            placeholder="Reps"
                            value={editReps}
                            onChange={(e) => setEditReps(e.target.value)}
                            className="block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-primary-500 focus:outline-none"
                          />
                          <div className="flex gap-1">
                            <button
                              onClick={handleSave}
                              disabled={saving}
                              className="flex-1 rounded bg-primary-600 px-2 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                            >
                              {saving ? "…" : "Salvar"}
                            </button>
                            {editing.existingId && (
                              <button
                                onClick={handleDelete}
                                disabled={saving}
                                className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-200 disabled:opacity-50"
                              >
                                ×
                              </button>
                            )}
                            <button
                              onClick={closeEdit}
                              className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-200"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      </td>
                    );
                  }

                  return (
                    <td
                      key={wod.id}
                      onClick={() => openEdit(team.id, wod.id)}
                      className={`px-4 py-3 text-center text-sm ${
                        canEdit ? "cursor-pointer hover:bg-primary-50" : ""
                      }`}
                    >
                      {result ? (
                        <div className="space-y-0.5">
                          {result.time_seconds != null && (
                            <div className="font-mono text-gray-900">
                              {formatTime(result.time_seconds)}
                            </div>
                          )}
                          {result.reps != null && (
                            <div className="text-xs text-gray-500">{result.reps} reps</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-300">{canEdit ? "+" : "—"}</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

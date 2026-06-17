import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { competitionsApi } from "../api/competitions";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Alert from "../components/ui/Alert";
import type { Competition } from "../types";

const STATUS_LABEL: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  draft: { label: "Rascunho", variant: "gray" },
  active: { label: "Ativa", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  hyrox: "Hyrox",
  crossfit: "CrossFit",
};

function formatDateRange(start: string | null, end: string | null): string {
  if (!start) return "—";
  const fmt = (d: string) =>
    new Date(d + "T00:00:00").toLocaleDateString("pt-BR");
  return end ? `${fmt(start)} → ${fmt(end)}` : fmt(start);
}

export default function CompetitionsListPage() {
  const navigate = useNavigate();
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    competitionsApi
      .list()
      .then((r) => setCompetitions(Array.isArray(r) ? r : (r as any).data ?? []))
      .catch(() => setError("Erro ao carregar campeonatos"))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: number) {
    if (!window.confirm("Remover este campeonato? Esta ação não pode ser desfeita.")) return;
    try {
      await competitionsApi.delete(id);
      setCompetitions((prev) => prev.filter((c) => c.id !== id));
    } catch {
      setError("Erro ao remover campeonato");
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campeonatos</h1>
          <p className="mt-1 text-sm text-gray-500">
            {competitions.length} campeonato{competitions.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Button
          onClick={() => navigate("/competitions/new")}
          className="flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          Novo Campeonato
        </Button>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {competitions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
          <p className="text-gray-500">Nenhum campeonato cadastrado.</p>
          <Button
            variant="secondary"
            className="mt-4"
            onClick={() => navigate("/competitions/new")}
          >
            Criar primeiro campeonato
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Nome
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Data
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Tipo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {competitions.map((comp) => {
                const statusInfo = STATUS_LABEL[comp.status] ?? { label: comp.status, variant: "gray" as const };
                return (
                  <tr key={comp.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <span className="font-medium text-gray-900">{comp.name}</span>
                      {comp.location && (
                        <p className="text-xs text-gray-500">{comp.location}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {formatDateRange(comp.start_date, comp.end_date)}
                    </td>
                    <td className="px-6 py-4">
                      {comp.event_type ? (
                        <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                          {EVENT_TYPE_LABEL[comp.event_type] ?? comp.event_type}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-3">
                        <button
                          onClick={() => navigate(`/competitions/${comp.id}/dashboard`)}
                          className="text-sm font-medium text-primary-600 hover:text-primary-800"
                        >
                          Dashboard
                        </button>
                        <button
                          onClick={() => navigate(`/competitions/${comp.id}/edit`)}
                          className="text-sm font-medium text-gray-600 hover:text-gray-800"
                        >
                          Editar
                        </button>
                        {comp.status === "draft" && (
                          <button
                            onClick={() => handleDelete(comp.id)}
                            className="text-sm font-medium text-red-600 hover:text-red-800"
                          >
                            Remover
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

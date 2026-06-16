import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { teamsApi } from "../../api/teams";
import { categoriesApi } from "../../api/categories";
import { athletesApi } from "../../api/athletes";
import type { Competition } from "../../types";

interface OutletCtx {
  competition: Competition;
}

function daysUntil(dateStr: string | null): string {
  if (!dateStr) return "—";
  const diff = Math.ceil(
    (new Date(dateStr + "T00:00:00").getTime() - Date.now()) / 86400000
  );
  if (diff < 0) return "Encerrado";
  if (diff === 0) return "Hoje";
  return `${diff} dia${diff !== 1 ? "s" : ""}`;
}

export default function DashboardOverviewPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const { competition } = useOutletContext<OutletCtx>();
  const [teamCount, setTeamCount] = useState<number | null>(null);
  const [athleteCount, setAthleteCount] = useState<number | null>(null);
  const [categoryCount, setCategoryCount] = useState<number | null>(null);

  useEffect(() => {
    const id = Number(competitionId);
    teamsApi.list(id).then((d) => setTeamCount(d.length));
    athletesApi.list(id).then((r: any) => setAthleteCount((r.data ?? r).length));
    categoriesApi.list(id).then((d) => setCategoryCount(d.length));
  }, [competitionId]);

  const EVENT_LABEL: Record<string, string> = { hyrox: "Hyrox", crossfit: "CrossFit" };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{competition.name}</h1>
        {competition.location && (
          <p className="mt-1 text-sm text-gray-500">{competition.location}</p>
        )}
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Dias para início", value: daysUntil(competition.start_date) },
          { label: "Equipes", value: teamCount ?? "…" },
          { label: "Atletas", value: athleteCount ?? "…" },
          { label: "Categorias", value: categoryCount ?? "…" },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg border border-gray-200 bg-white p-5">
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
            <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Informações do evento */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 font-semibold text-gray-900">Informações do Evento</h2>
        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Tipo</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {competition.event_type
                ? EVENT_LABEL[competition.event_type] ?? competition.event_type
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Pontuação</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {competition.scoring_model === "lowest_time"
                ? "Menor Tempo"
                : competition.scoring_model === "most_points"
                ? "Mais Pontos"
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Inscrições</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {competition.is_public ? "Públicas" : "Fechadas"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Desempate</dt>
            <dd className="mt-1 text-sm text-gray-900 capitalize">
              {competition.tiebreak_criterion?.replace(/_/g, " ") ?? "—"}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

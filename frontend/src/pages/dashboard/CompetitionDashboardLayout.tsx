import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import {
  ChartBarIcon,
  UserGroupIcon,
  PlayIcon,
  TrophyIcon,
  ArrowLeftIcon,
} from "@heroicons/react/24/outline";
import { competitionsApi } from "../../api/competitions";
import Badge from "../../components/ui/Badge";
import type { Competition } from "../../types";
import { useAuthStore } from "../../store/auth";

const STATUS_VARIANT: Record<string, "gray" | "green" | "red"> = {
  draft: "gray",
  active: "green",
  finished: "red",
};
const STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho",
  active: "Ativa",
  finished: "Encerrada",
};

const NAV_ITEMS = [
  { to: "", label: "Visão Geral", icon: ChartBarIcon, end: true },
  { to: "equipes", label: "Equipes", icon: UserGroupIcon, end: false },
  { to: "atletas", label: "Atletas", icon: UserGroupIcon, end: false },
  { to: "baterias", label: "Baterias", icon: PlayIcon, end: false },
  { to: "resultados", label: "Resultados", icon: TrophyIcon, end: false },
];

export default function CompetitionDashboardLayout() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const canManage = user?.role === "admin" || user?.role === "operator";
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [statusSaving, setStatusSaving] = useState(false);

  useEffect(() => {
    if (!competitionId) return;
    competitionsApi.get(Number(competitionId)).then((r: any) => {
      setCompetition(r.data ?? r);
    });
  }, [competitionId]);

  async function handleAdvanceStatus(newStatus: "active" | "finished") {
    if (!competition) return;
    if (newStatus === "finished" && !confirm("Encerrar a competição? Esta ação não pode ser revertida.")) return;
    setStatusSaving(true);
    try {
      const updated: any = await competitionsApi.update(competition.id, { status: newStatus });
      setCompetition(updated.data ?? updated);
    } finally {
      setStatusSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar escura */}
      <aside className="flex w-52 flex-col bg-slate-900 text-white">
        {/* Voltar + nome */}
        <div className="border-b border-slate-700 p-4">
          <button
            onClick={() => navigate("/competitions")}
            className="mb-3 flex items-center gap-1 text-xs text-slate-400 hover:text-white"
          >
            <ArrowLeftIcon className="h-3 w-3" /> Campeonatos
          </button>
          {competition ? (
            <>
              <p className="text-sm font-semibold leading-tight">{competition.name}</p>
              <div className="mt-1">
                <Badge variant={STATUS_VARIANT[competition.status]}>
                  {STATUS_LABEL[competition.status]}
                </Badge>
              </div>
              {canManage && competition.status === "draft" && (
                <button
                  onClick={() => handleAdvanceStatus("active")}
                  disabled={statusSaving}
                  className="mt-2 w-full rounded-md bg-green-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {statusSaving ? "Aguarde..." : "▶ Iniciar Competição"}
                </button>
              )}
              {canManage && competition.status === "active" && (
                <button
                  onClick={() => handleAdvanceStatus("finished")}
                  disabled={statusSaving}
                  className="mt-2 w-full rounded-md bg-red-700 px-2 py-1.5 text-xs font-medium text-white hover:bg-red-800 disabled:opacity-50"
                >
                  {statusSaving ? "Aguarde..." : "■ Encerrar Competição"}
                </button>
              )}
            </>
          ) : (
            <div className="h-4 w-32 animate-pulse rounded bg-slate-700" />
          )}
        </div>

        {/* Navegação */}
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to || "overview"}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Leaderboard público */}
        <div className="border-t border-slate-700 p-3">
          <a
            href={`/competitions/${competitionId}/ranking`}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-md px-3 py-2 text-xs text-slate-400 hover:text-white"
          >
            🔗 Leaderboard público
          </a>
        </div>
      </aside>

      {/* Conteúdo */}
      <main className="flex-1 overflow-auto bg-gray-50 p-8">
        {competition ? (
          <Outlet context={{ competition }} />
        ) : (
          <div className="flex justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
          </div>
        )}
      </main>
    </div>
  );
}

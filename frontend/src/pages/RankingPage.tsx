import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, TrophyIcon, ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { competitionsApi } from "../api/competitions";
import { rankingApi } from "../api/timers";
import { categoriesApi } from "../api/categories";
import { Card } from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import type { Category, Competition, RankingEntry } from "../types";
import { secondsToDisplay } from "../utils/time";

const STATUS_BADGE: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  draft: { label: "Rascunho", variant: "gray" },
  active: { label: "Ao Vivo", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

const TIMER_STATUS_BADGE: Record<string, { label: string; color: "green" | "yellow" | "gray" }> = {
  running: { label: "Ao vivo", color: "green" },
  stopped: { label: "Parado", color: "yellow" },
  finished: { label: "Finalizado", color: "gray" },
  idle: { label: "Aguardando", color: "gray" },
};

export default function RankingPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);

  const [competition, setCompetition] = useState<Competition | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | undefined>();
  const [ranking, setRanking] = useState<RankingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const loadRanking = useCallback(async () => {
    try {
      const data = await rankingApi.get(id, selectedCategory);
      setRanking(data);
    } catch {
      // silencioso — dados já exibidos
    }
  }, [id, selectedCategory]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [comp, cats] = await Promise.all([
          competitionsApi.getById(id),
          categoriesApi.list(id, true),
        ]);
        setCompetition(comp);
        setCategories(cats);
        const rankData = await rankingApi.get(id);
        setRanking(rankData);
      } catch {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    }
    if (!isNaN(id)) load();
    else setNotFound(true);
  }, [id]);

  // Re-carrega ranking quando muda filtro de categoria
  useEffect(() => {
    if (!loading) loadRanking();
  }, [selectedCategory, loadRanking, loading]);

  // Polling a cada 10s se competição ativa
  useEffect(() => {
    if (competition?.status !== "active") return;
    const interval = setInterval(loadRanking, 10000);
    return () => clearInterval(interval);
  }, [competition?.status, loadRanking]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Carregando ranking...</p>
      </div>
    );
  }

  if (notFound || !competition) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col items-center justify-center gap-4">
        <TrophyIcon className="h-12 w-12 text-gray-300" />
        <p className="text-gray-500 font-medium">Competição não encontrada.</p>
        <Link to="/" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
          Voltar ao início
        </Link>
      </div>
    );
  }

  const { label, variant } = STATUS_BADGE[competition.status] ?? STATUS_BADGE.draft;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-gray-900 text-white">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-4 transition-colors">
            <ArrowLeftIcon className="h-4 w-4" />
            Voltar
          </Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold">{competition.name}</h1>
              <p className="text-gray-400 text-sm mt-1">
                {competition.modality ?? "—"} · {competition.location ?? "—"}
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <Badge variant={variant}>{label}</Badge>
              <a
                href={rankingApi.exportCsvUrl(id)}
                className="inline-flex items-center gap-1 text-xs text-gray-300 hover:text-white border border-gray-600 px-3 py-1.5 rounded transition-colors"
              >
                <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                CSV
              </a>
              <a
                href={rankingApi.exportPdfUrl(id)}
                className="inline-flex items-center gap-1 text-xs text-gray-300 hover:text-white border border-gray-600 px-3 py-1.5 rounded transition-colors"
              >
                <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                PDF
              </a>
            </div>
          </div>

          {/* Filtro de categoria */}
          {categories.length > 1 && (
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory(undefined)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!selectedCategory ? "bg-white text-gray-900" : "bg-gray-700 text-gray-300 hover:bg-gray-600"}`}
              >
                Todas
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${selectedCategory === cat.id ? "bg-white text-gray-900" : "bg-gray-700 text-gray-300 hover:bg-gray-600"}`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <Card padding="none">
          <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center gap-2">
            <TrophyIcon className="h-5 w-5 text-yellow-500" />
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">Classificação Geral</h2>
            {competition.status === "active" && (
              <span className="ml-auto flex items-center gap-1.5 text-xs text-green-600">
                <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                Ao vivo
              </span>
            )}
          </div>

          {ranking.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <TrophyIcon className="h-10 w-10 text-gray-200 mx-auto mb-3" />
              <p className="text-gray-400 text-sm">
                {competition.status === "draft"
                  ? "A competição ainda não foi iniciada."
                  : "Nenhum resultado disponível ainda."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-800">
                    {["Pos.", "Atleta / Equipe", "Categoria", "Cronometrado", "Penalidades", "Tempo Final", "Status"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {ranking.map((entry) => {
                    const statusInfo = TIMER_STATUS_BADGE[entry.status];
                    return (
                      <tr key={entry.timer_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-4">
                          <span className={[
                            "inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                            entry.position === 1 ? "bg-yellow-100 text-yellow-700" :
                            entry.position === 2 ? "bg-gray-100 text-gray-700" :
                            entry.position === 3 ? "bg-orange-100 text-orange-700" :
                            "text-gray-500",
                          ].join(" ")}>
                            {entry.position || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-4 font-medium text-gray-900 dark:text-white">
                          {entry.athlete_name}
                        </td>
                        <td className="px-4 py-4 text-gray-500 dark:text-gray-400">
                          {entry.category_name ?? "—"}
                        </td>
                        <td className="px-4 py-4 font-mono text-gray-700 dark:text-gray-300">
                          {secondsToDisplay(entry.elapsed_seconds)}
                        </td>
                        <td className="px-4 py-4">
                          {entry.total_penalty_seconds > 0 ? (
                            <span className="text-red-500">+{entry.total_penalty_seconds}s</span>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-4 font-mono font-bold text-gray-900 dark:text-white">
                          {secondsToDisplay(entry.final_seconds)}
                        </td>
                        <td className="px-4 py-4">
                          <Badge variant={statusInfo.color}>{statusInfo.label}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}

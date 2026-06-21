import { useEffect, useState, useCallback } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeftIcon, TrophyIcon, ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { competitionsApi } from "../api/competitions";
import { adminApi } from "../api/admin";
import { rankingApi } from "../api/timers";
import { wodResultsApi } from "../api/wod_results";
import { categoriesApi } from "../api/categories";
import { Card } from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import type { Category, Competition, CrossfitRankingEntry, RankingEntry, WodLeaderboard } from "../types";
import { secondsToDisplay } from "../utils/time";
import { useAuthStore } from "../store/auth";

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

function formatRemaining(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds <= 0) return "00:00:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function formatSeconds(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0)
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ─── RankingSelectPage (sem competitionId na URL) ────────────────────────────

function RankingSelector() {
  const navigate = useNavigate();
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [hasLogo, setHasLogo] = useState(false);

  useEffect(() => {
    competitionsApi
      .list()
      .then(({ data }) => setCompetitions(data))
      .catch(() => {})
      .finally(() => setLoading(false));
    adminApi.getSettings().then(({ data }) => setHasLogo(data.has_logo)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-primary-700">
      <header className="bg-primary-700 text-white">
        <div className="max-w-5xl mx-auto px-4 py-6">
          {hasLogo && (
            <img
              src={adminApi.getLogoUrl()}
              alt="Logo"
              className="h-10 object-contain mb-3"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <div className="flex items-center gap-3 mb-2">
            <TrophyIcon className="h-7 w-7 text-yellow-400" />
            <h1 className="text-2xl font-bold">Ranking</h1>
          </div>
          <p className="text-primary-200 text-sm">Selecione uma competição para visualizar o ranking.</p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-10">
        <Card>
          {loading ? (
            <p className="text-gray-400 text-sm text-center py-8">Carregando competições...</p>
          ) : competitions.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">Nenhuma competição encontrada.</p>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 dark:text-gray-400 font-medium">Competição</p>
              <div className="flex items-center gap-3">
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                >
                  <option value="">Selecione uma competição...</option>
                  {competitions.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                      {c.status === "active" ? " — Ao Vivo" : c.status === "finished" ? " — Encerrada" : " — Rascunho"}
                    </option>
                  ))}
                </select>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={selectedId === ""}
                  onClick={() => { if (selectedId !== "") navigate(`/competitions/${selectedId}/ranking`); }}
                >
                  Ver Ranking
                </Button>
              </div>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}

// ─── RankingPage ──────────────────────────────────────────────────────────────

export default function RankingPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);
  const { user } = useAuthStore();

  // Quando acessado em /ranking (sem parâmetro), exibe seletor de competição
  if (!competitionId) {
    return <RankingSelector />;
  }

  const [competition, setCompetition] = useState<Competition | null>(null);
  const [hasLogo, setHasLogo] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | undefined>();
  const [ranking, setRanking] = useState<RankingEntry[]>([]);
  const [crossfitRanking, setCrossfitRanking] = useState<CrossfitRankingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [wodLeaderboard, setWodLeaderboard] = useState<WodLeaderboard | null>(null);

  const isCrossfit = competition?.event_type === "crossfit";

  const loadRanking = useCallback(async () => {
    try {
      if (isCrossfit) {
        const [data, leaderboard] = await Promise.all([
          rankingApi.getCrossfit(id, selectedCategory),
          wodResultsApi.getLeaderboard(id).catch(() => null),
        ]);
        setCrossfitRanking(data);
        if (leaderboard) setWodLeaderboard(leaderboard);
      } else {
        const [data, leaderboard] = await Promise.all([
          rankingApi.get(id, selectedCategory),
          wodResultsApi.getLeaderboard(id).catch(() => null),
        ]);
        setRanking(data);
        if (leaderboard) setWodLeaderboard(leaderboard);
      }
    } catch {
      // silencioso — dados já exibidos
    }
  }, [id, selectedCategory, isCrossfit]);

  useEffect(() => {
    adminApi.getSettings().then(({ data }) => setHasLogo(data.has_logo)).catch(() => {});
  }, []);

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
        if (comp.event_type === "crossfit") {
          const [rankData, leaderboard] = await Promise.all([
            rankingApi.getCrossfit(id),
            wodResultsApi.getLeaderboard(id).catch(() => null),
          ]);
          setCrossfitRanking(rankData);
          if (leaderboard) setWodLeaderboard(leaderboard);
        } else {
          const [rankData, leaderboard] = await Promise.all([
            rankingApi.get(id),
            wodResultsApi.getLeaderboard(id).catch(() => null),
          ]);
          setRanking(rankData);
          if (leaderboard) setWodLeaderboard(leaderboard);
        }
      } catch {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    }
    if (!isNaN(id)) load();
    else setNotFound(true);
  }, [id]);

  useEffect(() => {
    if (!loading) loadRanking();
  }, [selectedCategory, loadRanking, loading]);

  useEffect(() => {
    if (competition?.status !== "active") return;
    const interval = setInterval(loadRanking, 10000);
    return () => clearInterval(interval);
  }, [competition?.status, loadRanking]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-primary-700 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Carregando ranking...</p>
      </div>
    );
  }

  if (notFound || !competition) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-primary-700 flex flex-col items-center justify-center gap-4">
        <TrophyIcon className="h-12 w-12 text-gray-300" />
        <p className="text-gray-500 font-medium">Competição não encontrada.</p>
        <Link to="/" className="text-primary-600 hover:text-primary-700 text-sm font-medium">
          Voltar ao início
        </Link>
      </div>
    );
  }

  const { label, variant } = STATUS_BADGE[competition.status] ?? STATUS_BADGE.draft;
  const hasRemaining = ranking.some((e) => e.remaining_seconds !== null);
  const hasBoxName = ranking.some((e) => e.box_name != null && e.box_name !== "");

  const CROSSFIT_STATUS_LABEL: Record<string, string> = {
    finished: "Finalizado",
    running: "Ao vivo",
    paused: "Pausado",
    created: "Aguardando",
    ready: "Pronto",
    pending: "Aguardando",
    cancelled: "Cancelado",
  };
  const CROSSFIT_STATUS_VARIANT: Record<string, "gray" | "green" | "yellow"> = {
    finished: "gray",
    running: "green",
    paused: "yellow",
    created: "gray",
    ready: "gray",
    pending: "gray",
    cancelled: "gray",
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-primary-700">
      <header className="bg-primary-700 text-white">
        <div className="max-w-5xl mx-auto px-4 py-6">
          {hasLogo && (
            <img
              src={adminApi.getLogoUrl()}
              alt="Logo"
              className="h-10 object-contain mb-3"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-4 transition-colors">
            <ArrowLeftIcon className="h-4 w-4" />
            Voltar
          </Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold">{competition.name}</h1>
              <p className="text-primary-200 text-sm mt-1">
                {competition.event_type ? competition.event_type.toUpperCase() : "—"} · {competition.location ?? "—"}
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <Badge variant={variant}>{label}</Badge>
              <a
                href={isCrossfit ? rankingApi.exportCrossfiCsvUrl(id) : rankingApi.exportCsvUrl(id)}
                className="inline-flex items-center gap-1 text-xs text-primary-100 hover:text-white border border-primary-400 px-3 py-1.5 rounded transition-colors"
              >
                <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                CSV
              </a>
              <a
                href={isCrossfit ? rankingApi.exportCrossfiPdfUrl(id) : rankingApi.exportPdfUrl(id)}
                className="inline-flex items-center gap-1 text-xs text-primary-100 hover:text-white border border-primary-400 px-3 py-1.5 rounded transition-colors"
              >
                <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                PDF
              </a>
            </div>
          </div>

          {categories.length > 1 && (
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory(undefined)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!selectedCategory ? "bg-white text-primary-700" : "bg-primary-600 text-white hover:bg-primary-500"}`}
              >
                Todas
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${selectedCategory === cat.id ? "bg-white text-primary-700" : "bg-primary-600 text-white hover:bg-primary-500"}`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {wodLeaderboard && wodLeaderboard.entries.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <TrophyIcon className="h-5 w-5 text-yellow-400" />
              <h2 className="text-lg font-bold text-white">Leaderboard WODs</h2>
            </div>
            <div className="overflow-x-auto rounded-xl border border-white/10 bg-primary-800/40">
              <table className="min-w-full divide-y divide-white/10 text-sm">
                <thead className="bg-white/5">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400 w-10">#</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400">Equipe</th>
                    {wodLeaderboard.entries[0]?.wod_entries.map((we) => (
                      <th key={we.wod_id} className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-400">
                        {we.wod_name}
                      </th>
                    ))}
                    <th className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-400">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {wodLeaderboard.entries.map((entry) => (
                    <tr key={entry.team_id} className="hover:bg-white/5">
                      <td className="px-4 py-3 text-sm font-bold text-yellow-400">{entry.position}º</td>
                      <td className="px-4 py-3 text-sm font-medium text-white">{entry.team_name}</td>
                      {entry.wod_entries.map((we) => (
                        <td key={we.wod_id} className="px-4 py-3 text-center text-sm text-gray-300">
                          {we.points === 0 && we.rank === null && we.reps === null && we.time_seconds === null ? (
                            <span className="text-gray-500 text-xs">N/A</span>
                          ) : we.wod_type === "amrap" ? (
                            we.reps != null
                              ? <span title={`${we.points} pts`}>{we.reps} reps <span className="text-xs text-gray-400">({we.points}pts)</span></span>
                              : <span className="text-gray-500">—</span>
                          ) : we.wod_type === "for_time" ? (
                            we.time_seconds != null
                              ? <span title={`${we.points} pts`}>
                                  {formatSeconds(we.time_seconds)}
                                  {we.reps != null && <span className="text-xs text-gray-400"> +{we.reps}r</span>}
                                  {" "}<span className="text-xs text-gray-400">({we.points}pts)</span>
                                </span>
                              : <span className="text-gray-500">—</span>
                          ) : (
                            <span className="text-gray-500 text-xs">N/D</span>
                          )}
                        </td>
                      ))}
                      <td className="px-4 py-3 text-center text-sm font-bold text-white">
                        {wodLeaderboard.scoring_model === "lowest_time"
                          ? formatSeconds(entry.total_points)
                          : `${entry.total_points} pts`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
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

          {/* ── CrossFit ranking ───────────────────────────────────────── */}
          {isCrossfit && (
            crossfitRanking.length === 0 ? (
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
                      {["Pos.", "Atleta / Equipe", "Categoria", "WODs Concluídos", "Pontos Total", "Status"].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {crossfitRanking.map((entry) => (
                      <tr key={`${entry.team_id ?? entry.user_id}`} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-4">
                          <span className={[
                            "inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                            entry.position === 1 ? "bg-yellow-100 text-yellow-700" :
                            entry.position === 2 ? "bg-gray-100 text-gray-700" :
                            entry.position === 3 ? "bg-orange-100 text-orange-700" :
                            "text-gray-500",
                          ].join(" ")}>
                            {entry.position}
                          </span>
                        </td>
                        <td className="px-4 py-4 font-medium text-gray-900 dark:text-white">
                          {entry.team_name ?? entry.athlete_name}
                        </td>
                        <td className="px-4 py-4 text-gray-500 dark:text-gray-400">
                          {entry.category_name ?? "—"}
                        </td>
                        <td className="px-4 py-4 text-center text-gray-700 dark:text-gray-300">
                          {entry.wods_completed}
                        </td>
                        <td className="px-4 py-4 text-center font-bold text-gray-900 dark:text-white">
                          {entry.total_points}
                        </td>
                        <td className="px-4 py-4">
                          <Badge variant={CROSSFIT_STATUS_VARIANT[entry.status] ?? "gray"}>
                            {CROSSFIT_STATUS_LABEL[entry.status] ?? entry.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}

          {/* ── Hyrox / genérico ranking ───────────────────────────────── */}
          {!isCrossfit && (
            ranking.length === 0 ? (
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
                      {[
                        "Pos.",
                        "Atleta / Equipe",
                        "Categoria",
                        ...(hasBoxName ? ["Box / CT"] : []),
                        "Cronometrado",
                        "Penalidades",
                        "Infrações",
                        ...(hasRemaining ? ["Tempo Restante"] : []),
                        "Tempo Final",
                        "Status",
                      ].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          {h}
                        </th>
                      ))}
                      {competition.status === "finished" && user && (
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Downloads
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {ranking.map((entry) => {
                      const statusInfo = TIMER_STATUS_BADGE[entry.status];
                      const displayName = entry.team_name ?? entry.athlete_name;
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
                            <div>{displayName}</div>
                            {entry.team_name && (
                              <div className="text-xs text-gray-400 mt-0.5">{entry.athlete_name}</div>
                            )}
                          </td>
                          <td className="px-4 py-4 text-gray-500 dark:text-gray-400">
                            {entry.category_name ?? "—"}
                          </td>
                          {hasBoxName && (
                            <td className="px-4 py-4 text-gray-500 dark:text-gray-400">
                              {entry.box_name ?? "—"}
                            </td>
                          )}
                          <td className="px-4 py-4 font-mono text-gray-700 dark:text-gray-300">
                            {secondsToDisplay(entry.elapsed_seconds)}
                          </td>
                          <td className="px-4 py-4">
                            {entry.total_penalty_seconds > 0 ? (
                              <span className="text-red-500">+{entry.total_penalty_seconds}s</span>
                            ) : "—"}
                          </td>
                          <td className="px-4 py-4 text-center">
                            {entry.infractions_count > 0 ? (
                              <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-red-100 text-red-700 text-xs font-bold">
                                {entry.infractions_count}
                              </span>
                            ) : (
                              <span className="text-gray-300">—</span>
                            )}
                          </td>
                          {hasRemaining && (
                            <td className="px-4 py-4 font-mono text-blue-600 dark:text-blue-400">
                              {formatRemaining(entry.remaining_seconds)}
                            </td>
                          )}
                          <td className="px-4 py-4 font-mono font-bold text-gray-900 dark:text-white">
                            {secondsToDisplay(entry.final_seconds)}
                          </td>
                          <td className="px-4 py-4">
                            <Badge variant={statusInfo.color}>{statusInfo.label}</Badge>
                          </td>
                          {competition.status === "finished" && user && (() => {
                            const canDownload =
                              (user.role === "operator" || user.role === "admin") ||
                              (user.role === "competitor" && entry.user_id === user.id);
                            return (
                              <td className="px-4 py-4">
                                {canDownload && entry.user_id != null ? (
                                  <div className="flex items-center gap-2">
                                    <a
                                      href={rankingApi.certificateUrl(id, entry.user_id)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white border border-gray-300 dark:border-gray-600 px-2 py-1 rounded transition-colors"
                                    >
                                      📄 Certificado
                                    </a>
                                    <a
                                      href={rankingApi.socialImageUrl(id, entry.user_id)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white border border-gray-300 dark:border-gray-600 px-2 py-1 rounded transition-colors"
                                    >
                                      🖼 Social
                                    </a>
                                  </div>
                                ) : (
                                  <span className="text-gray-300 dark:text-gray-600">—</span>
                                )}
                              </td>
                            );
                          })()}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          )}
        </Card>
      </main>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, TrophyIcon } from "@heroicons/react/24/outline";
import { competitionsApi } from "../api/competitions";
import { Card } from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import type { Competition } from "../types";

interface RankingEntry {
  position: number;
  athlete_name: string;
  category: string;
  time: string;
  penalties: number;
}

const STATUS_BADGE: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  draft: { label: "Rascunho", variant: "gray" },
  active: { label: "Ao Vivo", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

export default function RankingPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);

  const [competition, setCompetition] = useState<Competition | null>(null);
  const [ranking, setRanking] = useState<RankingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [compRes, rankRes] = await Promise.all([
          competitionsApi.get(id),
          competitionsApi.getRanking(id),
        ]);
        setCompetition(compRes.data);
        setRanking(rankRes.data?.ranking ?? []);
      } catch {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    }
    if (!isNaN(id)) load();
    else setNotFound(true);
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Carregando ranking...</p>
      </div>
    );
  }

  if (notFound || !competition) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
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
    <div className="min-h-screen bg-gray-50">
      {/* Header público */}
      <header className="bg-gray-900 text-white">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-4 transition-colors"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Voltar
          </Link>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">{competition.name}</h1>
              <p className="text-gray-400 text-sm mt-1">
                {competition.modality ?? "—"} · {competition.location ?? "—"}
              </p>
            </div>
            <Badge variant={variant}>{label}</Badge>
          </div>
        </div>
      </header>

      {/* Ranking */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        <Card padding="none">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <TrophyIcon className="h-5 w-5 text-yellow-500" />
            <h2 className="text-base font-semibold text-gray-900">Classificação Geral</h2>
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
                  <tr className="bg-gray-50">
                    {["Pos.", "Atleta / Equipe", "Categoria", "Tempo", "Penalidades"].map((h) => (
                      <th
                        key={h}
                        className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ranking.map((entry) => (
                    <tr key={entry.position} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <span
                          className={[
                            "inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
                            entry.position === 1
                              ? "bg-yellow-100 text-yellow-700"
                              : entry.position === 2
                                ? "bg-gray-100 text-gray-700"
                                : entry.position === 3
                                  ? "bg-orange-100 text-orange-700"
                                  : "text-gray-500",
                          ].join(" ")}
                        >
                          {entry.position}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-medium text-gray-900">
                        {entry.athlete_name}
                      </td>
                      <td className="px-6 py-4 text-gray-500">{entry.category}</td>
                      <td className="px-6 py-4 font-mono font-medium text-gray-900">
                        {entry.time}
                      </td>
                      <td className="px-6 py-4 text-gray-500">
                        {entry.penalties > 0 ? (
                          <span className="text-red-600">+{entry.penalties}s</span>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}

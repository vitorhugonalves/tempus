import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { timersApi, penaltyTypesApi } from "../api/timers";
import { categoriesApi } from "../api/categories";
import { competitionsApi } from "../api/competitions";
import { useAuthStore } from "../store/auth";
import { secondsToDisplay } from "../utils/time";
import type { Timer, PenaltyType, Category, Competition } from "../types";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import { Card } from "../components/ui/Card";

const STATUS_COLORS: Record<string, "green" | "yellow" | "red" | "gray" | "blue" | "purple"> = {
  idle: "gray",
  running: "green",
  stopped: "yellow",
  finished: "gray",
};

const STATUS_LABELS: Record<string, string> = {
  idle: "Aguardando",
  running: "Em andamento",
  stopped: "Parado",
  finished: "Finalizado",
};

interface TimerCardProps {
  timer: Timer;
  categories: Category[];
  penaltyTypes: PenaltyType[];
  athleteName: string;
  canControl: boolean;
  onAction: (action: "start" | "stop" | "finish" | "restart", timerId: number, note?: string) => Promise<void>;
  onPenalty: (timerId: number, penaltyTypeId: number, justification: string) => Promise<void>;
}

function TimerCard({ timer, categories, penaltyTypes, athleteName, canControl, onAction, onPenalty }: TimerCardProps) {
  const [elapsed, setElapsed] = useState(timer.elapsed_seconds);
  const [restartNote, setRestartNote] = useState("");
  const [penaltyTypeId, setPenaltyTypeId] = useState<number | "">("");
  const [justification, setJustification] = useState("");
  const [showPenaltyForm, setShowPenaltyForm] = useState(false);
  const [loading, setLoading] = useState(false);

  const categoryName = categories.find((c) => c.id === timer.category_id)?.name;

  useEffect(() => {
    if (timer.status !== "running") {
      setElapsed(timer.elapsed_seconds);
      return;
    }
    setElapsed(timer.elapsed_seconds);
    const interval = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [timer.elapsed_seconds, timer.status]);

  const handleAction = async (action: "start" | "stop" | "finish" | "restart") => {
    if (action === "restart" && !restartNote.trim()) return;
    setLoading(true);
    try {
      await onAction(action, timer.id, action === "restart" ? restartNote : undefined);
      if (action === "restart") setRestartNote("");
    } finally {
      setLoading(false);
    }
  };

  const handlePenalty = async () => {
    if (!penaltyTypeId || !justification.trim()) return;
    setLoading(true);
    try {
      await onPenalty(timer.id, Number(penaltyTypeId), justification);
      setPenaltyTypeId("");
      setJustification("");
      setShowPenaltyForm(false);
    } finally {
      setLoading(false);
    }
  };

  const finalTime = elapsed + timer.total_penalty_seconds;

  return (
    <Card className="relative">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="font-semibold text-gray-900 dark:text-white">{athleteName}</p>
          {categoryName && (
            <p className="text-xs text-gray-500 dark:text-gray-400">{categoryName}</p>
          )}
        </div>
        <Badge variant={STATUS_COLORS[timer.status]}>{STATUS_LABELS[timer.status]}</Badge>
      </div>

      <div className="text-center my-4">
        <span className={`font-mono text-4xl font-bold ${timer.status === "running" ? "text-green-500" : "text-gray-800 dark:text-gray-100"}`}>
          {secondsToDisplay(elapsed)}
        </span>
        {timer.total_penalty_seconds > 0 && (
          <p className="text-sm text-red-500 mt-1">
            +{timer.total_penalty_seconds}s penalidade → {secondsToDisplay(finalTime)} total
          </p>
        )}
      </div>

      {canControl && timer.status !== "finished" && (
        <div className="flex flex-wrap gap-2 justify-center">
          {(timer.status === "idle" || timer.status === "stopped") ? (
            <Button size="sm" onClick={() => handleAction("start")} disabled={loading}>
              ▶ Iniciar
            </Button>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => handleAction("stop")} disabled={loading}>
              ⏸ Parar
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => handleAction("finish")} disabled={loading}>
            ⏹ Finalizar
          </Button>
          {penaltyTypes.length > 0 && (
            <Button size="sm" variant="danger" onClick={() => setShowPenaltyForm((v) => !v)} disabled={loading}>
              ⚠ Penalidade
            </Button>
          )}
        </div>
      )}

      {canControl && timer.status !== "finished" && (
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            placeholder="Motivo para reiniciar..."
            value={restartNote}
            onChange={(e) => setRestartNote(e.target.value)}
            className="flex-1 text-sm border rounded px-2 py-1 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          />
          <Button size="sm" variant="secondary" onClick={() => handleAction("restart")} disabled={loading || !restartNote.trim()}>
            ↺ Reiniciar
          </Button>
        </div>
      )}

      {showPenaltyForm && (
        <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
          <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-2">Aplicar Penalidade</p>
          <select
            value={penaltyTypeId}
            onChange={(e) => setPenaltyTypeId(e.target.value ? Number(e.target.value) : "")}
            className="w-full text-sm border rounded px-2 py-1 mb-2 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          >
            <option value="">Selecione o tipo...</option>
            {penaltyTypes.map((pt) => (
              <option key={pt.id} value={pt.id}>
                {pt.name} (+{pt.seconds}s)
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Justificativa obrigatória..."
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            className="w-full text-sm border rounded px-2 py-1 mb-2 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          />
          <div className="flex gap-2">
            <Button size="sm" variant="danger" onClick={handlePenalty} disabled={!penaltyTypeId || !justification.trim() || loading}>
              Aplicar
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setShowPenaltyForm(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export default function TimersPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const { user } = useAuthStore();
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [timers, setTimers] = useState<Timer[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [penaltyTypes, setPenaltyTypes] = useState<PenaltyType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const compId = Number(competitionId);
  const canControl = user?.role === "judge" || user?.role === "operator" || user?.role === "admin";

  const loadData = useCallback(async () => {
    try {
      const [comp, timerList, catList, ptList] = await Promise.all([
        competitionsApi.getById(compId),
        timersApi.list(compId),
        categoriesApi.list(compId),
        penaltyTypesApi.list(compId),
      ]);
      setCompetition(comp);
      setTimers(timerList);
      setCategories(catList);
      setPenaltyTypes(ptList);
    } catch {
      setError("Erro ao carregar dados da competição");
    } finally {
      setLoading(false);
    }
  }, [compId]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleAction = async (
    action: "start" | "stop" | "finish" | "restart",
    timerId: number,
    note?: string
  ) => {
    const fn = timersApi[action] as (id: number, note?: string) => Promise<Timer>;
    const updated = await fn(timerId, note);
    setTimers((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  };

  const handlePenalty = async (timerId: number, penaltyTypeId: number, justification: string) => {
    await timersApi.applyPenalty(timerId, { penalty_type_id: penaltyTypeId, justification });
    const updated = await timersApi.get(timerId);
    setTimers((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  };

  if (loading) {
    return <div className="flex items-center justify-center h-48 text-gray-500">Carregando timers...</div>;
  }
  if (error) {
    return <div className="p-6 text-center text-red-600">{error}</div>;
  }

  const running = timers.filter((t) => t.status === "running");
  const idle = timers.filter((t) => t.status === "idle");
  const done = timers.filter((t) => t.status === "stopped" || t.status === "finished");

  const getAthleteName = (t: Timer) => {
    if (t.user_id) return `Atleta #${t.user_id}`;
    if (t.team_id) return `Equipe #${t.team_id}`;
    return `Timer #${t.id}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {competition?.name ?? "Competição"}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {timers.length} timer(s) · {running.length} em andamento
          </p>
        </div>
        <Link to={`/competitions/${compId}/ranking`}>
          <Button variant="secondary" size="sm">Ver Ranking</Button>
        </Link>
      </div>

      {timers.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          Nenhum timer cadastrado nesta competição.
        </div>
      )}

      {running.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-3">Em andamento ({running.length})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {running.map((t) => (
              <TimerCard key={t.id} timer={t} categories={categories} penaltyTypes={penaltyTypes}
                athleteName={getAthleteName(t)} canControl={canControl} onAction={handleAction} onPenalty={handlePenalty} />
            ))}
          </div>
        </section>
      )}

      {idle.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-3">Aguardando ({idle.length})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {idle.map((t) => (
              <TimerCard key={t.id} timer={t} categories={categories} penaltyTypes={penaltyTypes}
                athleteName={getAthleteName(t)} canControl={canControl} onAction={handleAction} onPenalty={handlePenalty} />
            ))}
          </div>
        </section>
      )}

      {done.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-3">Finalizados ({done.length})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {done.map((t) => (
              <TimerCard key={t.id} timer={t} categories={categories} penaltyTypes={penaltyTypes}
                athleteName={getAthleteName(t)} canControl={canControl} onAction={handleAction} onPenalty={handlePenalty} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

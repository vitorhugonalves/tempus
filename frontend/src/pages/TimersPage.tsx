import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { timersApi, penaltyTypesApi } from "../api/timers";
import { competitionsApi } from "../api/competitions";
import { teamsApi } from "../api/teams";
import { heatsApi } from "../api/heats";
import { useAuthStore } from "../store/auth";
import { secondsToDisplay } from "../utils/time";
import type { Timer, PenaltyType, Competition, Heat, TimerEvent } from "../types";
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

const HEAT_STATUS_COLORS: Record<string, "green" | "yellow" | "red" | "gray"> = {
  pending: "gray",
  running: "green",
  finished: "red",
};

const HEAT_STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  running: "Em andamento",
  finished: "Finalizado",
};

const EVENT_LABELS: Record<string, string> = {
  start: "Iniciado",
  stop: "Parado",
  restart: "Reiniciado",
  finish: "Finalizado",
};

// ─── TimerHistory ────────────────────────────────────────────────────────────

interface TimerHistoryProps {
  timerId: number;
}

function TimerHistory({ timerId }: TimerHistoryProps) {
  const [events, setEvents] = useState<TimerEvent[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    timersApi
      .events(timerId)
      .then((data) => setEvents(data))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [timerId]);

  if (loading) return <p className="text-xs text-gray-400 mt-1 px-1">Carregando histórico...</p>;
  if (!events || events.length === 0) return <p className="text-xs text-gray-400 mt-1 px-1">Nenhum evento registrado.</p>;

  return (
    <ul className="mt-1 divide-y divide-gray-100 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden text-xs">
      {events.map((ev) => (
        <li key={ev.id} className="flex items-center justify-between px-3 py-1.5 bg-white dark:bg-gray-800">
          <span className="font-medium text-gray-700 dark:text-gray-300">
            {EVENT_LABELS[ev.event_type] ?? ev.event_type}
          </span>
          <span className="text-gray-400 dark:text-gray-500 tabular-nums">
            {new Date(ev.created_at).toLocaleString("pt-BR")}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ─── TeamTimerCard ────────────────────────────────────────────────────────────

interface TeamTimerCardProps {
  timer: Timer;
  teamName: string;
  memberNames: string[];
  penaltyTypes: PenaltyType[];
  durationSeconds: number | null;
  canControl: boolean;
  onAction: (action: "stop" | "finish" | "restart", timerId: number, note?: string) => Promise<void>;
  onPenalty: (timerId: number, penaltyTypeId: number, justification: string) => Promise<void>;
}

function TeamTimerCard({
  timer,
  teamName,
  memberNames,
  penaltyTypes,
  durationSeconds,
  canControl,
  onAction,
  onPenalty,
}: TeamTimerCardProps) {
  const [elapsed, setElapsed] = useState(timer.elapsed_seconds);
  const [restartNote, setRestartNote] = useState("");
  const [penaltyTypeId, setPenaltyTypeId] = useState<number | "">("");
  const [justification, setJustification] = useState("");
  const [showPenaltyForm, setShowPenaltyForm] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (timer.status !== "running") {
      setElapsed(timer.elapsed_seconds);
      return;
    }
    // Sync to server elapsed time on every update
    setElapsed(timer.elapsed_seconds);
    const interval = setInterval(() => setElapsed((prev) => prev + 1), 1000);
    return () => clearInterval(interval);
  }, [timer.elapsed_seconds, timer.status]);

  const handleAction = async (action: "stop" | "finish" | "restart") => {
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
  const remaining = durationSeconds != null ? Math.max(0, durationSeconds - elapsed) : null;
  const isRunning = timer.status === "running";

  return (
    <div>
      <Card className={`relative ${isRunning ? "border-green-300 dark:border-green-700" : ""}`}>
        {/* Team name & members */}
        <div className="flex items-start justify-between mb-2">
          <div>
            <p className="font-semibold text-gray-900 dark:text-white">{teamName}</p>
            {memberNames.length > 0 && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {memberNames.join(", ")}
              </p>
            )}
          </div>
          <Badge variant={STATUS_COLORS[timer.status]}>{STATUS_LABELS[timer.status]}</Badge>
        </div>

        {/* Elapsed time */}
        <div className="text-center my-3">
          <span className={`font-mono text-4xl font-bold ${isRunning ? "text-green-500" : "text-gray-800 dark:text-gray-100"}`}>
            {secondsToDisplay(elapsed)}
          </span>
          {remaining !== null && isRunning && (
            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
              Restante: {secondsToDisplay(remaining)}
            </p>
          )}
          {timer.total_penalty_seconds > 0 && (
            <p className="text-xs text-red-500 mt-1">
              +{timer.total_penalty_seconds}s penalidade → {secondsToDisplay(finalTime)} total
            </p>
          )}
        </div>

        {/* Controls */}
        {canControl && timer.status !== "finished" && (
          <>
            <div className="flex flex-wrap gap-2 justify-center">
              {(timer.status === "running") && (
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

            <div className="mt-2 flex gap-2">
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
          </>
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

      {timer.status !== "idle" && (
        <div className="mt-1 px-1">
          <button
            type="button"
            className="text-xs text-primary-600 hover:text-primary-800 dark:text-primary-400 dark:hover:text-primary-300 underline-offset-2 hover:underline"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? "Ocultar histórico" : "Ver histórico"}
          </button>
          {showHistory && <TimerHistory timerId={timer.id} />}
        </div>
      )}
    </div>
  );
}

// ─── HeatSection ──────────────────────────────────────────────────────────────

interface HeatSectionProps {
  heat: Heat;
  timers: Timer[];
  penaltyTypes: PenaltyType[];
  membersByTeam: Map<number, string[]>;
  teamNameById: Map<number, string>;
  durationSeconds: number | null;
  canControl: boolean;
  onStartHeat: (heatId: number) => Promise<void>;
  onTimerAction: (action: "stop" | "finish" | "restart", timerId: number, note?: string) => Promise<void>;
  onPenalty: (timerId: number, penaltyTypeId: number, justification: string) => Promise<void>;
}

function HeatSection({
  heat,
  timers,
  penaltyTypes,
  membersByTeam,
  teamNameById,
  durationSeconds,
  canControl,
  onStartHeat,
  onTimerAction,
  onPenalty,
}: HeatSectionProps) {
  const [startingHeat, setStartingHeat] = useState(false);
  const [heatError, setHeatError] = useState<string | null>(null);

  const heatTimers = timers.filter((t) => t.heat_id === heat.id);

  const handleStartHeat = async () => {
    setHeatError(null);
    setStartingHeat(true);
    try {
      await onStartHeat(heat.id);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setHeatError(detail ?? "Erro ao iniciar bateria");
    } finally {
      setStartingHeat(false);
    }
  };

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{heat.name}</h2>
          <Badge variant={HEAT_STATUS_COLORS[heat.status]}>{HEAT_STATUS_LABELS[heat.status]}</Badge>
          <span className="text-sm text-gray-400">
            {heat.team_count} equipe(s) · {heatTimers.length} timer(s)
          </span>
        </div>
        {canControl && heat.status !== "finished" && (
          <Button
            size="sm"
            variant="primary"
            onClick={handleStartHeat}
            isLoading={startingHeat}
          >
            ▶ Iniciar Bateria
          </Button>
        )}
      </div>

      {heatError && (
        <p className="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded border border-red-200 dark:border-red-800">
          {heatError}
        </p>
      )}

      {heatTimers.length === 0 ? (
        <p className="text-sm text-gray-400 italic">
          {heat.team_count === 0
            ? "Nenhuma equipe vinculada. Adicione equipes em Competições → Baterias."
            : "Clique em \"Iniciar Bateria\" para criar e iniciar os timers das equipes."}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {heatTimers.map((t) => {
            const teamName = t.team_id ? (teamNameById.get(t.team_id) ?? `Equipe #${t.team_id}`) : `Timer #${t.id}`;
            const memberNames = t.team_id ? (membersByTeam.get(t.team_id) ?? []) : [];
            return (
              <TeamTimerCard
                key={t.id}
                timer={t}
                teamName={teamName}
                memberNames={memberNames}
                penaltyTypes={penaltyTypes}
                durationSeconds={durationSeconds}
                canControl={canControl}
                onAction={onTimerAction}
                onPenalty={onPenalty}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}

// ─── CompetitionSelector ──────────────────────────────────────────────────────

interface CompetitionSelectorProps {
  competitions: Competition[];
  loading: boolean;
  onSelect: (id: number) => void;
}

function CompetitionSelector({ competitions, loading, onSelect }: CompetitionSelectorProps) {
  const [selectedId, setSelectedId] = useState<number | "">("");

  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <p className="text-gray-500 text-sm">Selecione uma competição para visualizar os timers:</p>
      {loading ? (
        <p className="text-gray-400 text-sm">Carregando competições...</p>
      ) : (
        <div className="flex items-center gap-3">
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white min-w-[240px]"
          >
            <option value="">Selecione uma competição...</option>
            {competitions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.status === "active" ? "Ativa" : c.status === "finished" ? "Encerrada" : "Rascunho"})
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="primary"
            onClick={() => { if (selectedId !== "") onSelect(Number(selectedId)); }}
            disabled={selectedId === ""}
          >
            Abrir
          </Button>
        </div>
      )}
    </div>
  );
}

// ─── TimersPage ───────────────────────────────────────────────────────────────

export default function TimersPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const compId = competitionId ? Number(competitionId) : NaN;
  const noCompetition = isNaN(compId);

  const [allCompetitions, setAllCompetitions] = useState<Competition[]>([]);
  const [competitionsLoading, setCompetitionsLoading] = useState(false);
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [heats, setHeats] = useState<Heat[]>([]);
  const [timers, setTimers] = useState<Timer[]>([]);
  const [penaltyTypes, setPenaltyTypes] = useState<PenaltyType[]>([]);
  const [membersByTeam, setMembersByTeam] = useState<Map<number, string[]>>(new Map());
  const [teamNameById, setTeamNameById] = useState<Map<number, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canControl = user?.role === "judge" || user?.role === "operator" || user?.role === "admin";

  // Load all competitions for selector when no competition selected
  useEffect(() => {
    if (!noCompetition) return;
    setCompetitionsLoading(true);
    competitionsApi.list()
      .then(({ data }) => setAllCompetitions(data))
      .catch(() => {})
      .finally(() => setCompetitionsLoading(false));
  }, [noCompetition]);

  const loadData = useCallback(async () => {
    if (noCompetition) return;
    try {
      const [comp, heatList, timerList, ptList] = await Promise.all([
        competitionsApi.getById(compId),
        heatsApi.list(compId),
        timersApi.list(compId),
        penaltyTypesApi.list(compId),
      ]);
      setCompetition(comp);
      setHeats(heatList);
      setTimers(timerList);
      setPenaltyTypes(ptList);
    } catch {
      setError("Erro ao carregar dados da competição");
    } finally {
      setLoading(false);
    }
  }, [compId, noCompetition]);

  // Load team members (only once per competition)
  useEffect(() => {
    if (noCompetition) return;
    (async () => {
      try {
        const teams = await teamsApi.list(compId);
        const nameMap = new Map<number, string>();
        const membersMap = new Map<number, string[]>();
        await Promise.all(
          teams.map(async (team) => {
            nameMap.set(team.id, team.name);
            try {
              const members = await teamsApi.listMembers(compId, team.id);
              membersMap.set(team.id, members.map((m) => m.user_name));
            } catch {
              membersMap.set(team.id, []);
            }
          })
        );
        setTeamNameById(nameMap);
        setMembersByTeam(membersMap);
      } catch {
        // silencioso — nomes dos membros são opcionais
      }
    })();
  }, [compId, noCompetition]);

  useEffect(() => {
    setLoading(true);
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleStartHeat = async (heatId: number) => {
    await heatsApi.start(compId, heatId);
    await loadData();
  };

  const handleTimerAction = async (
    action: "stop" | "finish" | "restart",
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

  // Timers not associated to any heat
  const orphanTimers = timers.filter((t) => t.heat_id === null);

  if (noCompetition) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Timers</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Gerencie os timers das baterias</p>
        </div>
        <CompetitionSelector
          competitions={allCompetitions}
          loading={competitionsLoading}
          onSelect={(id) => navigate(`/competitions/${id}/timers`)}
        />
      </div>
    );
  }

  if (loading) {
    return <div className="flex items-center justify-center h-48 text-gray-500">Carregando timers...</div>;
  }
  if (error) {
    return <div className="p-6 text-center text-red-600">{error}</div>;
  }

  const runningCount = timers.filter((t) => t.status === "running").length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {competition?.name ?? "Competição"}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {heats.length} bateria(s) · {timers.length} timer(s) · {runningCount} em andamento
          </p>
        </div>
        <Link to={`/competitions/${compId}/ranking`}>
          <Button variant="secondary" size="sm">Ver Ranking</Button>
        </Link>
      </div>

      {/* Heats */}
      {heats.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p>Nenhuma bateria criada para esta competição.</p>
          <p className="text-sm mt-1">Crie baterias em <Link to="/competitions" className="text-primary-600 hover:underline">Competições</Link> e vincule equipes a elas.</p>
        </div>
      ) : (
        heats.map((heat) => (
          <HeatSection
            key={heat.id}
            heat={heat}
            timers={timers}
            penaltyTypes={penaltyTypes}
            membersByTeam={membersByTeam}
            teamNameById={teamNameById}
            durationSeconds={competition?.duration_seconds ?? null}
            canControl={canControl}
            onStartHeat={handleStartHeat}
            onTimerAction={handleTimerAction}
            onPenalty={handlePenalty}
          />
        ))
      )}

      {/* Timers without heat */}
      {orphanTimers.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300">Sem Bateria ({orphanTimers.length})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {orphanTimers.map((t) => {
              const teamName = t.team_id ? (teamNameById.get(t.team_id) ?? `Equipe #${t.team_id}`) : `Timer #${t.id}`;
              const memberNames = t.team_id ? (membersByTeam.get(t.team_id) ?? []) : [];
              return (
                <TeamTimerCard
                  key={t.id}
                  timer={t}
                  teamName={teamName}
                  memberNames={memberNames}
                  penaltyTypes={penaltyTypes}
                  durationSeconds={competition?.duration_seconds ?? null}
                  canControl={canControl}
                  onAction={handleTimerAction}
                  onPenalty={handlePenalty}
                />
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { competitionsApi } from "../api/competitions";
import { teamsApi } from "../api/teams";
import { useCompetitionSocket, WsStatus } from "../hooks/useCompetitionSocket";
import { msToDisplay } from "../utils/time";
import type { Timer, Competition } from "../types";
import Badge from "../components/ui/Badge";

const STATUS_COLORS: Record<string, "green" | "yellow" | "red" | "gray" | "blue"> = {
  running: "green",
  paused: "yellow",
  finished: "gray",
  created: "gray",
  ready: "blue",
  cancelled: "red",
};

const STATUS_LABELS: Record<string, string> = {
  running: "Em andamento",
  paused: "Pausado",
  finished: "Finalizado",
  created: "Aguardando",
  ready: "Pronto",
  cancelled: "Cancelado",
};

// ─── LiveTimerRow ─────────────────────────────────────────────────────────────

interface LiveTimerRowProps {
  timer: Timer;
  position: number;
  teamName: string;
  memberNames: string[];
}

function LiveTimerRow({ timer, position, teamName, memberNames }: LiveTimerRowProps) {
  const [displayMs, setDisplayMs] = useState(() =>
    timer.status === "running" && timer.started_at_ms != null
      ? timer.accumulated_ms + (Date.now() - timer.started_at_ms)
      : timer.accumulated_ms
  );
  const rafRef = useRef<number | null>(null);
  const prevSecondsRef = useRef(-1);

  useEffect(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    if (timer.status !== "running" || timer.started_at_ms == null) {
      setDisplayMs(timer.accumulated_ms);
      prevSecondsRef.current = -1;
      return;
    }

    const tick = () => {
      const live = timer.accumulated_ms + (Date.now() - timer.started_at_ms!);
      const secs = Math.floor(live / 1000);
      if (secs !== prevSecondsRef.current) {
        prevSecondsRef.current = secs;
        setDisplayMs(live);
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [timer.status, timer.accumulated_ms, timer.started_at_ms]);

  const isRunning = timer.status === "running";

  return (
    <div
      className={`flex items-center gap-4 px-4 py-3 rounded-lg border transition-all ${
        isRunning
          ? "border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/10"
          : "border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800"
      }`}
    >
      {/* Position */}
      <span className="w-8 text-center font-bold text-gray-400 text-sm">{position}</span>

      {/* Team info */}
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-gray-900 dark:text-white truncate">{teamName}</p>
        {memberNames.length > 0 && (
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
            {memberNames.join(", ")}
          </p>
        )}
      </div>

      {/* Status */}
      <Badge variant={STATUS_COLORS[timer.status] ?? "gray"}>
        {STATUS_LABELS[timer.status] ?? timer.status}
      </Badge>

      {/* Time */}
      <span
        className={`font-mono text-2xl font-bold tabular-nums w-28 text-right ${
          isRunning ? "text-green-600 dark:text-green-400" : "text-gray-700 dark:text-gray-200"
        }`}
      >
        {msToDisplay(displayMs)}
      </span>
    </div>
  );
}

// ─── WsStatusBadge ────────────────────────────────────────────────────────────

function WsStatusBadge({ status }: { status: WsStatus }) {
  const map: Record<WsStatus, { label: string; color: string }> = {
    connected: { label: "Ao vivo", color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" },
    connecting: { label: "Conectando…", color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" },
    disconnected: { label: "Desconectado", color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" },
  };
  const { label, color } = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${status === "connected" ? "bg-green-500 animate-pulse" : status === "connecting" ? "bg-yellow-500 animate-pulse" : "bg-red-500"}`} />
      {label}
    </span>
  );
}

// ─── LivePage ─────────────────────────────────────────────────────────────────

export default function LivePage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const compId = competitionId ? Number(competitionId) : NaN;

  const { timers, wsStatus, refreshFromRest } = useCompetitionSocket(isNaN(compId) ? null : compId);

  const [competition, setCompetition] = useState<Competition | null>(null);
  const [teamNameById, setTeamNameById] = useState<Map<number, string>>(new Map());
  const [membersByTeam, setMembersByTeam] = useState<Map<number, string[]>>(new Map());
  const [startOrderMap, setStartOrderMap] = useState<Map<number, number>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isNaN(compId)) return;
    Promise.all([
      competitionsApi.getById(compId),
      import("../api/timers").then((m) => m.timersApi.list(compId)),
    ]).then(([comp, timerList]) => {
      setCompetition(comp);
      refreshFromRest(timerList);
      // Build initial start order from started_at_ms (lower = started earlier)
      const orderMap = new Map<number, number>();
      const sorted = [...timerList]
        .filter((t) => t.started_at_ms != null || t.accumulated_ms > 0)
        .sort((a, b) => (a.started_at_ms ?? 0) - (b.started_at_ms ?? 0));
      sorted.forEach((t, i) => orderMap.set(t.id, i + 1));
      setStartOrderMap(orderMap);
      setLoading(false);
    }).catch(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compId]);

  // Load team names & members
  useEffect(() => {
    if (isNaN(compId)) return;
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
        // silencioso
      }
    })();
  }, [compId]);

  // Assign start order for newly started timers
  useEffect(() => {
    setStartOrderMap((prev) => {
      const updated = new Map(prev);
      let maxOrder = Math.max(0, ...Array.from(prev.values()));
      timers.forEach((t) => {
        if (!updated.has(t.id) && (t.status === "running" || t.status === "paused" || t.accumulated_ms > 0)) {
          maxOrder += 1;
          updated.set(t.id, maxOrder);
        }
      });
      return updated;
    });
  }, [timers]);

  // Show running and paused timers, sorted by start order
  const liveTimers = timers
    .filter((t) => t.status === "running" || t.status === "paused")
    .sort((a, b) => (startOrderMap.get(a.id) ?? 999) - (startOrderMap.get(b.id) ?? 999));

  if (isNaN(compId)) {
    return (
      <div className="p-8 text-center text-gray-500">
        Competição não especificada.{" "}
        <Link to="/timers" className="text-primary-600 hover:underline">Voltar</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {competition?.name ?? "Painel Ao Vivo"}
            </h1>
            <WsStatusBadge status={wsStatus} />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {liveTimers.length} timer(s) em andamento
          </p>
        </div>
        <Link
          to={`/competitions/${compId}/timers`}
          className="text-sm text-primary-600 hover:underline dark:text-primary-400"
        >
          ← Voltar para Timers
        </Link>
      </div>

      {/* Timer list */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">Carregando...</div>
      ) : liveTimers.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-4xl mb-4">⏱</p>
          <p className="text-gray-500 text-lg">Nenhum timer em andamento</p>
          <p className="text-gray-400 text-sm mt-1">
            Os timers aparecerão aqui assim que forem iniciados.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {liveTimers.map((t, idx) => {
            const teamName = t.team_id ? (teamNameById.get(t.team_id) ?? `Equipe #${t.team_id}`) : `Timer #${t.id}`;
            const memberNames = t.team_id ? (membersByTeam.get(t.team_id) ?? []) : [];
            return (
              <LiveTimerRow
                key={t.id}
                timer={t}
                position={idx + 1}
                teamName={teamName}
                memberNames={memberNames}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

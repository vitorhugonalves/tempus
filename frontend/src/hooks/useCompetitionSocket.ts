/**
 * Hook WebSocket para atualizações em tempo real de uma competição.
 *
 * Protocolo de mensagens do servidor:
 *   { type: "init", competition_id, timers: Timer[] }
 *   { type: "ping" }
 *   { event_type: "started"|"paused"|..., timer_id, accumulated_ms, started_at_ms }
 *
 * Reconexão automática com backoff exponencial (1 s → 30 s).
 *
 * `refreshFromRest(timers)` permite semear o estado com dados REST (ex.: após
 * criar novos timers via startHeat). O próximo `init` do WS substituirá o estado.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Timer } from "../types";

export type WsStatus = "connecting" | "connected" | "disconnected";

interface TimerEvent {
  event_type: string;
  timer_id: number;
  accumulated_ms?: number;
  started_at_ms?: number | null;
  [key: string]: unknown;
}

interface InitMessage {
  type: "init";
  competition_id: number;
  timers: Timer[];
}

type ServerMessage = InitMessage | { type: "ping" } | TimerEvent;

interface UseCompetitionSocketResult {
  timers: Timer[];
  wsStatus: WsStatus;
  /** Substitui o estado local de timers com dados vindos do REST (fallback ou pós-startHeat). */
  refreshFromRest: (timers: Timer[]) => void;
}

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;

function buildWsUrl(competitionId: number): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/competition/${competitionId}`;
}

/** Aplica evento de timer recebido via pub/sub ao array de timers local. */
function applyEvent(timers: Timer[], event: TimerEvent): Timer[] {
  return timers.map((t) => {
    if (t.id !== event.timer_id) return t;

    const updated = { ...t };

    if (event.accumulated_ms !== undefined) {
      updated.accumulated_ms = event.accumulated_ms;
    }
    if ("started_at_ms" in event) {
      updated.started_at_ms = (event.started_at_ms as number | null) ?? null;
    }

    switch (event.event_type) {
      case "started":
      case "resumed":
        updated.status = "running";
        break;
      case "paused":
        updated.status = "paused";
        updated.started_at_ms = null;
        break;
      case "finished":
        updated.status = "finished";
        updated.started_at_ms = null;
        break;
      case "reset":
        updated.status = "created";
        updated.accumulated_ms = 0;
        updated.started_at_ms = null;
        break;
      case "cancelled":
        updated.status = "cancelled";
        updated.started_at_ms = null;
        break;
      case "ready":
        updated.status = "ready";
        break;
    }

    return updated;
  });
}

export function useCompetitionSocket(
  competitionId: number | null
): UseCompetitionSocketResult {
  const [timers, setTimers] = useState<Timer[]>([]);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");

  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(BACKOFF_BASE_MS);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (competitionId === null || unmountedRef.current) return;

    const url = buildWsUrl(competitionId);
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      backoffRef.current = BACKOFF_BASE_MS;
      setWsStatus("connected");
    };

    ws.onmessage = (ev) => {
      if (unmountedRef.current) return;
      try {
        const msg: ServerMessage = JSON.parse(ev.data as string);
        if ("type" in msg) {
          if (msg.type === "init") {
            setTimers((msg as InitMessage).timers);
          }
          // ignore "ping"
          return;
        }
        // timer event
        setTimers((prev) => applyEvent(prev, msg as TimerEvent));
      } catch {
        // mensagem malformada — ignorar
      }
    };

    ws.onerror = () => {
      // onclose dispara logo após; reconexão tratada lá
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setWsStatus("disconnected");
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * 2, BACKOFF_MAX_MS);
      retryRef.current = setTimeout(connect, delay);
    };
  }, [competitionId]);

  useEffect(() => {
    unmountedRef.current = false;

    if (competitionId !== null) {
      connect();
    }

    return () => {
      unmountedRef.current = true;
      if (retryRef.current !== null) {
        clearTimeout(retryRef.current);
        retryRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [competitionId, connect]);

  return { timers, wsStatus, refreshFromRest: setTimers };
}

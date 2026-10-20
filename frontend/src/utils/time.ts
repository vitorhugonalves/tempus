/**
 * Utilitários de formatação de tempo.
 */

export function secondsToHMS(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export function secondsToDisplay(seconds: number): string {
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return secondsToHMS(seconds);
}

export function msToDisplay(ms: number): string {
  return secondsToDisplay(Math.floor(ms / 1000));
}

const MS_PER_SECOND = 1000;
const MS_PER_MINUTE = 60 * MS_PER_SECOND;
const MS_PER_HOUR = 60 * MS_PER_MINUTE;

// H:MM:SS ou HH:MM:SS, com até 3 casas de milésimos opcionais. Horas são
// obrigatórias: "78:00" seria ambíguo entre mm:ss e hh:mm.
const DURATION_PATTERN = /^(\d{1,2}):([0-5]\d):([0-5]\d)(?:\.(\d{1,3}))?$/;

/** Converte "HH:MM:SS(.mmm)" em milissegundos; retorna null se o formato for inválido. */
export function parseDurationToMs(input: string): number | null {
  const match = DURATION_PATTERN.exec(input.trim());
  if (!match) return null;
  const [, hours, minutes, seconds, fraction = ""] = match;
  // ".5" significa 500 ms, não 5 ms
  const millis = Number(fraction.padEnd(3, "0"));
  return (
    Number(hours) * MS_PER_HOUR +
    Number(minutes) * MS_PER_MINUTE +
    Number(seconds) * MS_PER_SECOND +
    millis
  );
}

/** Formata milissegundos como "HH:MM:SS.mmm" (precisão total, para conferência de ajustes). */
export function msToPreciseDisplay(ms: number): string {
  const millis = String(ms % MS_PER_SECOND).padStart(3, "0");
  return `${secondsToHMS(Math.floor(ms / MS_PER_SECOND))}.${millis}`;
}

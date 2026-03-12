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

import { useState } from "react";
import { Modal } from "../ui/Modal";
import Input from "../ui/Input";
import Button from "../ui/Button";
import Alert from "../ui/Alert";
import { msToPreciseDisplay, parseDurationToMs } from "../../utils/time";

// Espelham as constantes do backend (app/core/constants.py); o backend valida de novo.
const MIN_JUSTIFICATION_CHARS = 10;
const MAX_JUSTIFICATION_CHARS = 500;
const MAX_ADJUSTED_TIME_MS = 24 * 60 * 60 * 1000;

interface AdjustTimeModalProps {
  isOpen: boolean;
  teamName: string;
  currentTimeMs: number;
  onClose: () => void;
  onConfirm: (finalTimeMs: number, justification: string) => Promise<void>;
}

function validateTime(input: string): { ms: number | null; error?: string } {
  if (!input.trim()) return { ms: null };
  const ms = parseDurationToMs(input);
  if (ms === null) return { ms: null, error: "Use o formato HH:MM:SS ou HH:MM:SS.mmm" };
  if (ms <= 0) return { ms: null, error: "O tempo deve ser maior que zero" };
  if (ms > MAX_ADJUSTED_TIME_MS) return { ms: null, error: "O tempo não pode passar de 24h" };
  return { ms };
}

export default function AdjustTimeModal({
  isOpen,
  teamName,
  currentTimeMs,
  onClose,
  onConfirm,
}: AdjustTimeModalProps) {
  const [timeInput, setTimeInput] = useState("");
  const [justification, setJustification] = useState("");
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { ms: newTimeMs, error: timeError } = validateTime(timeInput);
  const justificationLength = justification.trim().length;
  const justificationIsValid = justificationLength >= MIN_JUSTIFICATION_CHARS;
  const canSubmit = newTimeMs !== null && justificationIsValid && !saving;

  const handleClose = () => {
    if (saving) return;
    setTimeInput("");
    setJustification("");
    setSubmitError(null);
    onClose();
  };

  const handleConfirm = async () => {
    if (newTimeMs === null || !justificationIsValid) return;
    setSaving(true);
    setSubmitError(null);
    try {
      await onConfirm(newTimeMs, justification.trim());
      setTimeInput("");
      setJustification("");
      onClose();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setSubmitError(typeof detail === "string" ? detail : "Erro ao ajustar o tempo");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={`Ajustar tempo — ${teamName}`}>
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Tempo atual: <span className="font-mono font-semibold">{msToPreciseDisplay(currentTimeMs)}</span>
        </p>

        <Input
          label="Novo tempo"
          placeholder="01:18:00"
          value={timeInput}
          onChange={(e) => setTimeInput(e.target.value)}
          error={timeError}
          hint="HH:MM:SS, milésimos opcionais (ex.: 01:18:00.250). Sem penalidades — elas continuam somadas à parte."
          autoFocus
        />

        <div>
          <label htmlFor="adjust-justification" className="block text-sm font-medium text-gray-700 mb-1">
            Justificativa
          </label>
          <textarea
            id="adjust-justification"
            rows={3}
            maxLength={MAX_JUSTIFICATION_CHARS}
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            placeholder="Ex.: timer finalizado por engano; tempo conferido no cronômetro manual"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-primary-500"
          />
          <p className={`mt-1 text-xs ${justificationIsValid || !justification ? "text-gray-500" : "text-red-600"}`}>
            Obrigatória, mínimo de {MIN_JUSTIFICATION_CHARS} caracteres ({justificationLength}/{MAX_JUSTIFICATION_CHARS}).
            Fica registrada no histórico do timer.
          </p>
        </div>

        {newTimeMs !== null && (
          <p className="rounded-lg bg-gray-50 border border-gray-200 px-3 py-2 text-sm font-mono text-gray-800">
            {msToPreciseDisplay(currentTimeMs)} → {msToPreciseDisplay(newTimeMs)}
          </p>
        )}

        {submitError && <Alert variant="error">{submitError}</Alert>}

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={handleClose} disabled={saving}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={handleConfirm} disabled={!canSubmit} isLoading={saving}>
            Confirmar ajuste
          </Button>
        </div>
      </div>
    </Modal>
  );
}

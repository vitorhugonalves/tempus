import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { competitionsApi, type CompetitionCreate } from "../api/competitions";
import { cepApi } from "../api/cep";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type { EventType, ScoringModel, TiebreakCriterion } from "../types";

// ── Tipos do estado local ─────────────────────────────────────────────────────

interface WizardStep1 {
  name: string;
  start_date: string;
  end_date: string;
  cep: string;
  logradouro: string;
  bairro: string;
  cidade: string;
  uf: string;
  numero: string;
  complemento: string;
  event_type: EventType | "";
}

interface WizardStep4 {
  scoring_model: ScoringModel | "";
  tiebreak_criterion: TiebreakCriterion | "";
}

interface WizardState {
  step1: WizardStep1;
  step4: WizardStep4;
}

const INITIAL_STATE: WizardState = {
  step1: {
    name: "",
    start_date: "",
    end_date: "",
    cep: "",
    logradouro: "",
    bairro: "",
    cidade: "",
    uf: "",
    numero: "",
    complemento: "",
    event_type: "",
  },
  step4: { scoring_model: "", tiebreak_criterion: "" },
};

// ── Componente principal ──────────────────────────────────────────────────────

export default function CompetitionWizardPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [currentStep, setCurrentStep] = useState(1);
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [cepLoading, setCepLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    competitionsApi.get(Number(id)).then((r: any) => {
      const c = r.data ?? r;
      setState((prev) => ({
        ...prev,
        step1: {
          name: c.name ?? "",
          start_date: c.start_date ?? "",
          end_date: c.end_date ?? "",
          cep: "",
          logradouro: c.location ?? "",
          bairro: "",
          cidade: "",
          uf: "",
          numero: "",
          complemento: "",
          event_type: c.event_type ?? "",
        },
        step4: {
          scoring_model: c.scoring_model ?? "",
          tiebreak_criterion: c.tiebreak_criterion ?? "",
        },
      }));
    });
  }, [id]);

  // ── CEP lookup ─────────────────────────────────────────────────────────────

  async function handleCepBlur() {
    const digits = state.step1.cep.replace(/\D/g, "");
    if (digits.length !== 8) return;
    setCepLoading(true);
    try {
      const result: any = await cepApi.lookup(digits);
      const d = result.data ?? result;
      setState((prev) => ({
        ...prev,
        step1: {
          ...prev.step1,
          logradouro: d.logradouro ?? "",
          bairro: d.bairro ?? "",
          cidade: d.localidade ?? "",
          uf: d.uf ?? "",
        },
      }));
    } catch {
      // CEP inválido — usuário preenche manualmente
    } finally {
      setCepLoading(false);
    }
  }

  // ── Validação por etapa ────────────────────────────────────────────────────

  function validateStep1(): string | null {
    if (!state.step1.name.trim()) return "Nome do campeonato é obrigatório";
    if (!state.step1.event_type) return "Selecione o tipo de evento (Hyrox ou CrossFit)";
    return null;
  }

  function validateStep4(): string | null {
    if (!state.step4.scoring_model) return "Selecione o modelo de pontuação";
    return null;
  }

  function handleNext() {
    setError(null);
    if (currentStep === 1) {
      const err = validateStep1();
      if (err) { setError(err); return; }
    }
    if (currentStep === 4) {
      const err = validateStep4();
      if (err) { setError(err); return; }
    }
    setCurrentStep((s) => Math.min(s + 1, 5));
  }

  function handleBack() {
    setError(null);
    setCurrentStep((s) => Math.max(s - 1, 1));
  }

  // ── Submissão final ────────────────────────────────────────────────────────

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    const locationParts = [
      state.step1.logradouro,
      state.step1.numero,
      state.step1.bairro,
      state.step1.cidade,
      state.step1.uf,
    ].filter(Boolean);

    const payload: CompetitionCreate = {
      name: state.step1.name,
      location: locationParts.join(", ") || undefined,
      start_date: state.step1.start_date || undefined,
      end_date: state.step1.end_date || undefined,
      event_type: (state.step1.event_type as EventType) || undefined,
      scoring_model: (state.step4.scoring_model as ScoringModel) || undefined,
      tiebreak_criterion: (state.step4.tiebreak_criterion as TiebreakCriterion) || undefined,
    };

    try {
      let result: any;
      if (isEdit && id) {
        result = await competitionsApi.update(Number(id), payload);
      } else {
        result = await competitionsApi.create(payload);
      }
      const comp = result.data ?? result;
      navigate(`/competitions/${comp.id}/dashboard`);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao salvar campeonato");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render por etapa ───────────────────────────────────────────────────────

  const STEPS = ["Informações", "Divulgação", "WODs", "Pontuação", "Finalização"];

  return (
    <div className="mx-auto max-w-3xl space-y-8 py-8">
      {/* Breadcrumb de etapas */}
      <nav className="flex flex-wrap gap-2">
        {STEPS.map((label, i) => {
          const step = i + 1;
          const done = step < currentStep;
          const active = step === currentStep;
          return (
            <div key={step} className="flex items-center gap-2">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  done
                    ? "bg-primary-600 text-white"
                    : active
                    ? "border-2 border-primary-600 text-primary-600"
                    : "border-2 border-gray-300 text-gray-400"
                }`}
              >
                {step}
              </div>
              <span className={`text-sm ${active ? "font-medium text-gray-900" : "text-gray-400"}`}>
                {label}
              </span>
              {i < STEPS.length - 1 && <div className="h-px w-6 bg-gray-300" />}
            </div>
          );
        })}
      </nav>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Etapa 1: Informações Gerais */}
      {currentStep === 1 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Informações Gerais</h2>

          <div className="space-y-4">
            <Input
              label="Nome do campeonato *"
              value={state.step1.name}
              onChange={(e) =>
                setState((p) => ({ ...p, step1: { ...p.step1, name: e.target.value } }))
              }
            />
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Data de início"
                type="date"
                value={state.step1.start_date}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, start_date: e.target.value } }))
                }
              />
              <Input
                label="Data de término"
                type="date"
                value={state.step1.end_date}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, end_date: e.target.value } }))
                }
              />
            </div>
          </div>

          {/* Local / CEP */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-700">Local do evento</h3>
            <div className="grid grid-cols-3 gap-4">
              <Input
                label="CEP"
                value={state.step1.cep}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, cep: e.target.value } }))
                }
                onBlur={handleCepBlur}
                placeholder="00000-000"
              />
              {cepLoading && (
                <div className="flex items-end pb-2">
                  <span className="text-sm text-gray-400">Buscando...</span>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Logradouro"
                value={state.step1.logradouro}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, logradouro: e.target.value } }))
                }
              />
              <Input
                label="Número"
                value={state.step1.numero}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, numero: e.target.value } }))
                }
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Input
                label="Bairro"
                value={state.step1.bairro}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, bairro: e.target.value } }))
                }
              />
              <Input
                label="Cidade"
                value={state.step1.cidade}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, cidade: e.target.value } }))
                }
              />
              <Input
                label="UF"
                value={state.step1.uf}
                maxLength={2}
                onChange={(e) =>
                  setState((p) => ({
                    ...p,
                    step1: { ...p.step1, uf: e.target.value.toUpperCase() },
                  }))
                }
              />
            </div>
          </div>

          {/* Tipo do evento */}
          <div className="space-y-3 border-t pt-4">
            <h3 className="font-medium text-gray-700">Tipo de evento *</h3>
            <div className="grid grid-cols-2 gap-4">
              {(["hyrox", "crossfit"] as EventType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() =>
                    setState((p) => ({ ...p, step1: { ...p.step1, event_type: type } }))
                  }
                  className={`rounded-lg border-2 p-4 text-left transition-colors ${
                    state.step1.event_type === type
                      ? "border-primary-600 bg-primary-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <p className="font-semibold text-gray-900 capitalize">{type}</p>
                  <p className="text-sm text-gray-500">
                    {type === "hyrox"
                      ? "Corrida + Estações de Funcional"
                      : "WODs com pontuação por posição"}
                  </p>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Categorias podem ser adicionadas após a criação no dashboard do campeonato.
          </div>
        </div>
      )}

      {/* Etapas 2 e 3 — placeholder para fases futuras */}
      {(currentStep === 2 || currentStep === 3) && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
          <p className="text-gray-500">
            {currentStep === 2
              ? "Etapa 2 (Divulgação) — disponível na Fase 2 do redesenho."
              : "Etapa 3 (WODs) — disponível na Fase 3 do redesenho (somente CrossFit)."}
          </p>
        </div>
      )}

      {/* Etapa 4: Pontuação */}
      {currentStep === 4 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Modelo de Pontuação</h2>

          <div className="grid grid-cols-2 gap-4">
            {(
              [
                { value: "lowest_time" as ScoringModel, label: "Menor Tempo", desc: "Vence quem terminar mais rápido" },
                { value: "most_points" as ScoringModel, label: "Mais Pontos", desc: "Vence quem acumular mais pontos" },
              ] as const
            ).map(({ value, label, desc }) => (
              <button
                key={value}
                type="button"
                onClick={() =>
                  setState((p) => ({ ...p, step4: { ...p.step4, scoring_model: value } }))
                }
                className={`rounded-lg border-2 p-4 text-left transition-colors ${
                  state.step4.scoring_model === value
                    ? "border-primary-600 bg-primary-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <p className="font-semibold text-gray-900">{label}</p>
                <p className="text-sm text-gray-500">{desc}</p>
              </button>
            ))}
          </div>

          <div className="space-y-3 border-t pt-4">
            <h3 className="font-medium text-gray-700">Critério de desempate</h3>
            {(
              [
                { value: "last_checkpoint" as TiebreakCriterion, label: "Último checkpoint" },
                { value: "registration_date" as TiebreakCriterion, label: "Data de inscrição" },
                { value: "alphabetical" as TiebreakCriterion, label: "Ordem alfabética" },
              ] as const
            ).map(({ value, label }) => (
              <label key={value} className="flex cursor-pointer items-center gap-3">
                <input
                  type="radio"
                  name="tiebreak"
                  value={value}
                  checked={state.step4.tiebreak_criterion === value}
                  onChange={() =>
                    setState((p) => ({
                      ...p,
                      step4: { ...p.step4, tiebreak_criterion: value },
                    }))
                  }
                  className="h-4 w-4 text-primary-600"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Etapa 5: Resumo e criação */}
      {currentStep === 5 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Resumo</h2>

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Nome</p>
              <p className="mt-1 font-medium text-gray-900">{state.step1.name || "—"}</p>
            </div>
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Tipo</p>
              <p className="mt-1 font-medium text-gray-900 capitalize">
                {state.step1.event_type || "—"}
              </p>
            </div>
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Data</p>
              <p className="mt-1 font-medium text-gray-900">
                {state.step1.start_date || "—"}
                {state.step1.end_date ? ` → ${state.step1.end_date}` : ""}
              </p>
            </div>
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Pontuação</p>
              <p className="mt-1 font-medium text-gray-900">
                {state.step4.scoring_model === "lowest_time"
                  ? "Menor Tempo"
                  : state.step4.scoring_model === "most_points"
                  ? "Mais Pontos"
                  : "—"}
              </p>
            </div>
          </div>

          <Button onClick={handleSubmit} disabled={submitting} className="w-full justify-center">
            {submitting ? "Salvando..." : isEdit ? "Salvar Alterações" : "Criar Campeonato"}
          </Button>
        </div>
      )}

      {/* Navegação */}
      <div className="flex justify-between">
        <Button variant="secondary" onClick={handleBack} disabled={currentStep === 1}>
          Voltar
        </Button>
        {currentStep < 5 && (
          <Button onClick={handleNext}>
            {currentStep === 4 ? "Revisar" : "Avançar"}
          </Button>
        )}
      </div>
    </div>
  );
}

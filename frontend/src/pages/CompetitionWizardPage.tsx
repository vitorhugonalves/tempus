import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { competitionsApi, type CompetitionCreate, type WodCreate } from "../api/competitions";
import { cepApi } from "../api/cep";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type { EventType, ScoringModel, TiebreakCriterion, Wod, WodType } from "../types";

// ── Helpers de data ───────────────────────────────────────────────────────────

function ptDateToIso(ptDate: string): string {
  const match = ptDate.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return ptDate;
  return `${match[3]}-${match[2]}-${match[1]}`;
}

function isoToPtDate(iso: string): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

function applyDateMask(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length > 4) return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  if (digits.length > 2) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return digits;
}

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

interface WizardStep2 {
  is_public: boolean;
  description: string;
  regulations_url: string;
  registration_url: string;
  instagram_url: string;
  whatsapp_url: string;
}

interface WizardStep3 {
  wods: Wod[];
}

interface WizardStep4 {
  scoring_model: ScoringModel | "";
  tiebreak_criterion: TiebreakCriterion | "";
}

interface WizardState {
  step1: WizardStep1;
  step2: WizardStep2;
  step3: WizardStep3;
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
  step2: {
    is_public: false,
    description: "",
    regulations_url: "",
    registration_url: "",
    instagram_url: "",
    whatsapp_url: "",
  },
  step3: { wods: [] },
  step4: { scoring_model: "", tiebreak_criterion: "" },
};

// ── Componente principal ──────────────────────────────────────────────────────

export default function CompetitionWizardPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [currentStep, setCurrentStep] = useState(1);
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [startDateDisplay, setStartDateDisplay] = useState("");
  const [endDateDisplay, setEndDateDisplay] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [cepLoading, setCepLoading] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);
  const [bannerUploading, setBannerUploading] = useState(false);
  const [createdCompId, setCreatedCompId] = useState<number | null>(id ? Number(id) : null);
  const [wodAdding, setWodAdding] = useState(false);
  const [wodForm, setWodForm] = useState<WodCreate>({
    name: "",
    wod_type: "amrap",
    duration_minutes: undefined,
    description: "",
    order: 0,
  });

  useEffect(() => {
    if (!id) return;
    competitionsApi.get(Number(id)).then(async (r: any) => {
      const c = r.data ?? r;
      setStartDateDisplay(c.start_date ? isoToPtDate(c.start_date) : "");
      setEndDateDisplay(c.end_date ? isoToPtDate(c.end_date) : "");
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
      if (c.event_type === "crossfit") {
        const wodsResp = await competitionsApi.listWods(Number(id));
        const wods = (wodsResp.data ?? wodsResp) as Wod[];
        setState((prev) => ({ ...prev, step3: { wods } }));
      }
      setState((prev) => ({
        ...prev,
        step2: {
          is_public: c.is_public ?? false,
          description: c.description ?? "",
          regulations_url: c.regulations_url ?? "",
          registration_url: c.registration_url ?? "",
          instagram_url: c.instagram_url ?? "",
          whatsapp_url: c.whatsapp_url ?? "",
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
    // Pular Etapa 3 (WODs) para eventos Hyrox
    if (currentStep === 2 && state.step1.event_type === "hyrox") {
      setCurrentStep(4);
      return;
    }
    setCurrentStep((s) => Math.min(s + 1, 5));
  }

  function handleBack() {
    setError(null);
    // Pular Etapa 3 (WODs) ao voltar para Hyrox
    if (currentStep === 4 && state.step1.event_type === "hyrox") {
      setCurrentStep(2);
      return;
    }
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
      is_public: state.step2.is_public,
      description: state.step2.description || undefined,
      regulations_url: state.step2.regulations_url || undefined,
      registration_url: state.step2.registration_url || undefined,
      instagram_url: state.step2.instagram_url || undefined,
      whatsapp_url: state.step2.whatsapp_url || undefined,
    };

    try {
      let result: any;
      if (isEdit && id) {
        result = await competitionsApi.update(Number(id), payload);
      } else {
        result = await competitionsApi.create(payload);
      }
      const comp = result.data ?? result;
      setCreatedCompId(comp.id);
      navigate(`/competitions/${comp.id}/dashboard`);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao salvar campeonato");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Upload de imagens ──────────────────────────────────────────────────────

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !createdCompId) return;
    setLogoUploading(true);
    try {
      await competitionsApi.uploadLogo(createdCompId, file);
    } catch {
      setError("Erro ao fazer upload do logotipo.");
    } finally {
      setLogoUploading(false);
    }
  }

  async function handleBannerUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !createdCompId) return;
    setBannerUploading(true);
    try {
      await competitionsApi.uploadBanner(createdCompId, file);
    } catch {
      setError("Erro ao fazer upload do banner.");
    } finally {
      setBannerUploading(false);
    }
  }

  // ── Handlers de WOD ───────────────────────────────────────────────────────

  async function handleAddWod() {
    if (!wodForm.name.trim() || !createdCompId) return;
    setWodAdding(true);
    try {
      const resp = await competitionsApi.createWod(createdCompId, {
        ...wodForm,
        order: state.step3.wods.length,
      });
      const newWod = (resp.data ?? resp) as Wod;
      setState((p) => ({ ...p, step3: { wods: [...p.step3.wods, newWod] } }));
      setWodForm({ name: "", wod_type: "amrap", duration_minutes: undefined, description: "", order: 0 });
    } catch {
      setError("Erro ao adicionar WOD.");
    } finally {
      setWodAdding(false);
    }
  }

  async function handleDeleteWod(wodId: number) {
    if (!createdCompId) return;
    try {
      await competitionsApi.deleteWod(createdCompId, wodId);
      setState((p) => ({
        ...p,
        step3: { wods: p.step3.wods.filter((w) => w.id !== wodId) },
      }));
    } catch {
      setError("Erro ao remover WOD.");
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
                placeholder="dd/mm/aaaa"
                value={startDateDisplay}
                onChange={(e) => {
                  const masked = applyDateMask(e.target.value);
                  setStartDateDisplay(masked);
                  const iso = ptDateToIso(masked);
                  setState((p) => ({
                    ...p,
                    step1: { ...p.step1, start_date: iso !== masked ? iso : masked },
                  }));
                }}
              />
              <Input
                label="Data de término"
                placeholder="dd/mm/aaaa"
                value={endDateDisplay}
                onChange={(e) => {
                  const masked = applyDateMask(e.target.value);
                  setEndDateDisplay(masked);
                  const iso = ptDateToIso(masked);
                  setState((p) => ({
                    ...p,
                    step1: { ...p.step1, end_date: iso !== masked ? iso : masked },
                  }));
                }}
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

      {/* Etapa 2: Divulgação */}
      {currentStep === 2 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Divulgação</h2>

          {/* Visibilidade */}
          <div className="flex items-center gap-3">
            <input
              id="is_public"
              type="checkbox"
              checked={state.step2.is_public}
              onChange={(e) =>
                setState((p) => ({ ...p, step2: { ...p.step2, is_public: e.target.checked } }))
              }
              className="h-4 w-4 rounded border-gray-300 text-primary-600"
            />
            <label htmlFor="is_public" className="text-sm font-medium text-gray-700">
              Tornar esta competição pública (visível na página de ranking e inscrição)
            </label>
          </div>

          {/* Descrição */}
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">Descrição</label>
            <textarea
              rows={4}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              placeholder="Descreva o evento, formato, local e demais informações relevantes..."
              value={state.step2.description}
              onChange={(e) =>
                setState((p) => ({ ...p, step2: { ...p.step2, description: e.target.value } }))
              }
            />
          </div>

          {/* Links */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-700">Links</h3>
            <Input
              label="Regulamento (URL)"
              placeholder="https://..."
              value={state.step2.regulations_url}
              onChange={(e) =>
                setState((p) => ({ ...p, step2: { ...p.step2, regulations_url: e.target.value } }))
              }
            />
            <Input
              label="Inscrições externas (URL)"
              placeholder="https://..."
              value={state.step2.registration_url}
              onChange={(e) =>
                setState((p) => ({ ...p, step2: { ...p.step2, registration_url: e.target.value } }))
              }
            />
          </div>

          {/* Redes sociais */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-700">Redes sociais</h3>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Instagram"
                placeholder="https://instagram.com/..."
                value={state.step2.instagram_url}
                onChange={(e) =>
                  setState((p) => ({ ...p, step2: { ...p.step2, instagram_url: e.target.value } }))
                }
              />
              <Input
                label="WhatsApp"
                placeholder="https://wa.me/55..."
                value={state.step2.whatsapp_url}
                onChange={(e) =>
                  setState((p) => ({ ...p, step2: { ...p.step2, whatsapp_url: e.target.value } }))
                }
              />
            </div>
          </div>

          {/* Upload de imagens */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-700">Imagens</h3>
            {!createdCompId && (
              <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
                Upload disponível após criar a competição (Etapa 5).
              </p>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">Logotipo</label>
                {createdCompId && (
                  <img
                    src={`/api/v1/competitions/${createdCompId}/logo`}
                    alt="Logo"
                    className="h-16 w-auto rounded border border-gray-200 object-contain"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                )}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/gif,image/webp"
                  disabled={!createdCompId || logoUploading}
                  onChange={handleLogoUpload}
                  className="block w-full text-sm text-gray-500 file:mr-3 file:rounded file:border-0 file:bg-primary-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-primary-700 disabled:opacity-50"
                />
                {logoUploading && <p className="text-xs text-gray-400">Enviando...</p>}
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">Banner</label>
                {createdCompId && (
                  <img
                    src={`/api/v1/competitions/${createdCompId}/banner`}
                    alt="Banner"
                    className="h-16 w-auto rounded border border-gray-200 object-contain"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                )}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/gif,image/webp"
                  disabled={!createdCompId || bannerUploading}
                  onChange={handleBannerUpload}
                  className="block w-full text-sm text-gray-500 file:mr-3 file:rounded file:border-0 file:bg-primary-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-primary-700 disabled:opacity-50"
                />
                {bannerUploading && <p className="text-xs text-amber-600">Enviando...</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Etapa 3: WODs (apenas CrossFit) */}
      {currentStep === 3 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">WODs</h2>

          {/* Lista de WODs existentes */}
          {state.step3.wods.length === 0 && (
            <p className="text-sm text-gray-500">Nenhum WOD cadastrado ainda.</p>
          )}
          {state.step3.wods.map((wod) => (
            <div key={wod.id} className="flex items-start justify-between rounded-md border border-gray-200 p-4">
              <div className="space-y-1">
                <p className="font-medium text-gray-900">{wod.name}</p>
                <p className="text-xs text-gray-500">
                  {wod.wod_type.replace("_", " ").toUpperCase()}
                  {wod.duration_minutes ? ` · ${wod.duration_minutes} min` : ""}
                </p>
                {wod.description && (
                  <p className="text-sm text-gray-600">{wod.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleDeleteWod(wod.id)}
                className="ml-4 text-red-500 hover:text-red-700"
                title="Remover WOD"
              >
                &#128465;
              </button>
            </div>
          ))}

          {/* Formulário de novo WOD */}
          <div className="space-y-4 rounded-md border border-dashed border-gray-300 p-4">
            <h3 className="text-sm font-medium text-gray-700">Adicionar WOD</h3>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Nome *"
                placeholder="Ex: Fran"
                value={wodForm.name}
                onChange={(e) => setWodForm((f) => ({ ...f, name: e.target.value }))}
              />
              <div className="space-y-1">
                <label className="block text-sm font-medium text-gray-700">Tipo *</label>
                <select
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none"
                  value={wodForm.wod_type}
                  onChange={(e) => setWodForm((f) => ({ ...f, wod_type: e.target.value as WodType }))}
                >
                  <option value="amrap">AMRAP</option>
                  <option value="for_time">For Time</option>
                  <option value="emom">EMOM</option>
                  <option value="max_load">Max Load</option>
                </select>
              </div>
            </div>
            <Input
              label="Duração (minutos)"
              type="number"
              placeholder="Ex: 20"
              value={wodForm.duration_minutes ?? ""}
              onChange={(e) =>
                setWodForm((f) => ({
                  ...f,
                  duration_minutes: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            />
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-700">Movimentos</label>
              <textarea
                rows={3}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                placeholder="Ex: 21-15-9 Thrusters (43 kg) + Pull-ups"
                value={wodForm.description ?? ""}
                onChange={(e) => setWodForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <Button
              onClick={handleAddWod}
              disabled={!wodForm.name.trim() || wodAdding || !createdCompId}
              variant="secondary"
            >
              {wodAdding ? "Adicionando..." : "+ Adicionar WOD"}
            </Button>
            {!createdCompId && (
              <p className="text-xs text-amber-600">
                WODs disponíveis após criar a competição (Etapa 5).
              </p>
            )}
          </div>
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
                {startDateDisplay || "—"}
                {endDateDisplay ? ` → ${endDateDisplay}` : ""}
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
            {/* Card: Visibilidade */}
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Visibilidade</p>
              <p className="mt-1 font-medium text-gray-900">
                {state.step2.is_public ? "Pública" : "Privada"}
              </p>
            </div>
            {/* Card: WODs (só CrossFit) */}
            {state.step1.event_type === "crossfit" && (
              <div className="rounded-md bg-gray-50 p-4">
                <p className="text-xs font-medium uppercase text-gray-500">WODs</p>
                <p className="mt-1 font-medium text-gray-900">
                  {state.step3.wods.length > 0
                    ? `${state.step3.wods.length} WOD(s) cadastrado(s)`
                    : "Nenhum WOD"}
                </p>
              </div>
            )}
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

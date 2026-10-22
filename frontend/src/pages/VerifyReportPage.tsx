import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { isAxiosError } from "axios";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import { reportsApi } from "../api/reports";
import type { ReportType, ReportVerification } from "../types";

const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  ranking: "Ranking de tempo",
  wod_leaderboard: "Leaderboard WODs",
};

const ROLE_LABELS: Record<string, string> = {
  admin: "Administração",
  operator: "Operação",
};

type LookupState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "found"; result: ReportVerification }
  | { kind: "not_found" }
  | { kind: "error"; message: string };

// Data e hora separadas: toLocaleString("pt-BR") insere vírgula ("22/10/2026, 12:30:00").
function formatBrasilia(isoUtc: string): string {
  const date = new Date(isoUtc);
  const options = { timeZone: "America/Sao_Paulo" } as const;
  return `${date.toLocaleDateString("pt-BR", options)} ${date.toLocaleTimeString("pt-BR", options)}`;
}

function lookupErrorState(error: unknown): LookupState {
  if (isAxiosError(error) && error.response?.status === 404) return { kind: "not_found" };
  if (isAxiosError(error) && error.response?.status === 413) {
    return { kind: "error", message: "Arquivo grande demais (máximo 10 MB)." };
  }
  if (isAxiosError(error) && error.response?.status === 422) {
    return { kind: "error", message: "O arquivo enviado não é um PDF." };
  }
  return { kind: "error", message: "Não foi possível verificar agora. Tente novamente." };
}

interface VerificationResultProps {
  result: ReportVerification;
}

function VerificationResult({ result }: VerificationResultProps) {
  const authentic = result.status === "valid";
  return (
    <Card>
      <Alert
        variant={authentic ? "success" : "error"}
        title={authentic ? "Documento autêntico" : "Documento adulterado"}
      >
        {authentic
          ? "Este relatório foi emitido pelo Tempus e não foi alterado desde a emissão."
          : "O registro deste relatório não confere com a assinatura digital. Não confie neste documento e contate a organização."}
      </Alert>
      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="font-medium text-gray-500">Competição</dt>
        <dd>{result.competition_name}</dd>
        <dt className="font-medium text-gray-500">Relatório</dt>
        <dd>{REPORT_TYPE_LABELS[result.report_type]}</dd>
        <dt className="font-medium text-gray-500">Categoria</dt>
        <dd>{result.category_name ?? "Todas"}</dd>
        <dt className="font-medium text-gray-500">Gerado em</dt>
        <dd>{formatBrasilia(result.issued_at)} (horário de Brasília)</dd>
        <dt className="font-medium text-gray-500">Emitido por</dt>
        <dd>{ROLE_LABELS[result.issued_by_role ?? ""] ?? "—"}</dd>
        <dt className="font-medium text-gray-500">Código</dt>
        <dd className="font-mono">{result.verification_code}</dd>
        <dt className="font-medium text-gray-500">SHA-256</dt>
        <dd className="break-all font-mono text-xs">{result.sha256}</dd>
      </dl>
      {authentic && (
        <a
          href={reportsApi.originalPdfUrl(result.verification_code)}
          className="mt-4 inline-block rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          Baixar original
        </a>
      )}
    </Card>
  );
}

export default function VerifyReportPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<LookupState>({ kind: "idle" });
  const [typedCode, setTypedCode] = useState("");

  useEffect(() => {
    if (!code) {
      setState({ kind: "idle" });
      return;
    }
    setState({ kind: "loading" });
    reportsApi
      .verifyByCode(code)
      .then((result) => setState({ kind: "found", result }))
      .catch((error: unknown) => setState(lookupErrorState(error)));
  }, [code]);

  const handleCodeSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = typedCode.trim();
    if (trimmed) navigate(`/verificar/${encodeURIComponent(trimmed)}`);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setState({ kind: "loading" });
    reportsApi
      .verifyByFile(file)
      .then((result) => setState({ kind: "found", result }))
      .catch((error: unknown) => setState(lookupErrorState(error)));
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Verificar relatório</h1>
        <p className="text-sm text-gray-600">
          Confira se um PDF de ranking foi emitido pelo Tempus e não foi alterado.
        </p>

        <Card>
          <form onSubmit={handleCodeSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Input
                id="verification-code"
                label="Código de verificação"
                value={typedCode}
                onChange={(e) => setTypedCode(e.target.value)}
                placeholder="Impresso no rodapé do PDF"
              />
            </div>
            <Button type="submit">Verificar</Button>
          </form>
          <div className="mt-4">
            <label htmlFor="verify-file" className="block text-sm font-medium text-gray-700">
              Ou envie o arquivo PDF
            </label>
            <input
              id="verify-file"
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="mt-1 block w-full text-sm"
            />
          </div>
        </Card>

        {state.kind === "loading" && <p className="text-sm text-gray-500">Verificando…</p>}
        {state.kind === "found" && <VerificationResult result={state.result} />}
        {state.kind === "not_found" && (
          <Alert variant="warning" title="Não encontrado">
            Este código ou arquivo não corresponde a nenhum relatório emitido pelo Tempus. Se o
            arquivo foi editado, mesmo que minimamente, ele deixa de corresponder.
          </Alert>
        )}
        {state.kind === "error" && <Alert variant="error">{state.message}</Alert>}
      </div>
    </div>
  );
}

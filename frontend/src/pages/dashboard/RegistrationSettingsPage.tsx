import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { consentTermApi, type ConsentTermMeta } from "../../api/consentTerm";
import { Card } from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Alert from "../../components/ui/Alert";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR");
}

export default function RegistrationSettingsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);
  const fileRef = useRef<HTMLInputElement>(null);

  const [meta, setMeta] = useState<ConsentTermMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadMeta() {
    return consentTermApi
      .get(id)
      .then(setMeta)
      .catch(() => setError("Erro ao carregar termo de consentimento"));
  }

  useEffect(() => {
    setLoading(true);
    loadMeta().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setError(null);
    setUploading(true);
    try {
      await consentTermApi.upload(id, file);
      if (fileRef.current) fileRef.current.value = "";
      await loadMeta();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao enviar termo de consentimento");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Remover o termo de consentimento atual?")) return;
    setError(null);
    try {
      await consentTermApi.delete(id);
      await loadMeta();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao remover termo de consentimento");
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Inscrição</h1>

      {error && <Alert variant="error">{error}</Alert>}

      <Card>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Termo de consentimento
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Se um termo for cadastrado, os competidores precisarão aceitá-lo para
          concluir a inscrição pública nesta competição.
        </p>

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
          </div>
        ) : (
          <div className="space-y-4">
            {meta?.has_term ? (
              <div className="rounded-lg bg-gray-50 p-4">
                <p className="text-sm font-medium text-gray-900">{meta.file_name}</p>
                {meta.uploaded_at && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    Enviado em {formatDateTime(meta.uploaded_at)}
                  </p>
                )}
                <div className="flex gap-3 mt-3">
                  <a
                    href={consentTermApi.fileUrl(id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-primary-600 hover:underline"
                  >
                    Ver termo atual
                  </a>
                  <button
                    type="button"
                    onClick={handleDelete}
                    className="text-sm font-medium text-red-600 hover:underline"
                  >
                    Remover
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400">
                Nenhum termo de consentimento cadastrado. Sem um termo, a
                inscrição não exige nenhum aceite.
              </p>
            )}

            <form onSubmit={handleUpload} className="flex items-end gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {meta?.has_term ? "Substituir termo (PDF)" : "Enviar termo (PDF)"}
                </label>
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/pdf"
                  className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-primary-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-700 hover:file:bg-primary-100"
                />
              </div>
              <Button type="submit" isLoading={uploading}>
                Enviar
              </Button>
            </form>
          </div>
        )}
      </Card>
    </div>
  );
}

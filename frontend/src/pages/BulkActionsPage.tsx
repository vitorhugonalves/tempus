import { useRef, useState } from "react";
import { adminApi, type BulkImportResult } from "../api/admin";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Alert from "../components/ui/Alert";

type Tab = "users" | "teams";

export default function BulkActionsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("users");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BulkImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleTabChange(tab: Tab) {
    setActiveTab(tab);
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setResult(null);
    setError(null);
  }

  async function handleImport() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { data } =
        activeTab === "users"
          ? await adminApi.bulkImportUsers(file)
          : await adminApi.bulkImportTeams(file);
      setResult(data);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Erro ao importar arquivo. Verifique o formato e tente novamente.");
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setFile(null);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Importação em Lote</h1>
        <p className="text-gray-500 text-sm mt-1">
          Importe usuários ou equipes em massa via arquivo CSV.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-6">
          {(["users", "teams"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => handleTabChange(tab)}
              className={[
                "py-3 text-sm font-medium border-b-2 transition-colors",
                activeTab === tab
                  ? "border-primary-600 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
              ].join(" ")}
            >
              {tab === "users" ? "Usuários" : "Equipes"}
            </button>
          ))}
        </nav>
      </div>

      {/* Instruções */}
      <Card>
        <h2 className="text-sm font-semibold text-gray-900 mb-2">Formato do CSV</h2>
        {activeTab === "users" ? (
          <>
            <p className="text-sm text-gray-600 mb-3">
              Cada linha representa um usuário. Separador: ponto-e-vírgula (<code>;</code>).
              Cabeçalho é opcional.
            </p>
            <pre className="bg-gray-50 rounded p-3 text-xs text-gray-700 overflow-x-auto">
{`nome_completo;email;perfil
João Silva;joao@example.com;competitor
Maria Santos;maria@example.com;judge
Carlos Alves;carlos@example.com;operator`}
            </pre>
            <p className="text-xs text-gray-400 mt-2">
              Perfis aceitos: <strong>competitor</strong>, <strong>judge</strong>,{" "}
              <strong>operator</strong>, <strong>admin</strong>. Uma senha aleatória é gerada para
              cada usuário.
            </p>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-600 mb-3">
              Cada linha representa uma equipe. Separador: ponto-e-vírgula (<code>;</code>).
              Cabeçalho é opcional.
            </p>
            <pre className="bg-gray-50 rounded p-3 text-xs text-gray-700 overflow-x-auto">
{`id_competicao;categoria_equipe;nome_equipe;email_competidor_01;email_competidor_02
1;Dupla Mista;Equipe Alpha;joao@example.com;maria@example.com
1;Dupla Mista;Equipe Beta;carlos@example.com;ana@example.com`}
            </pre>
            <p className="text-xs text-gray-400 mt-2">
              Validações: competição deve existir; categoria deve pertencer à competição; nome da
              equipe deve ser único; todos os e-mails devem ser de usuários cadastrados; a
              quantidade de e-mails deve ser igual ao tamanho máximo da categoria.
            </p>
          </>
        )}
      </Card>

      {/* Upload e Importação */}
      <Card>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Arquivo CSV
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
            />
          </div>

          {error && <Alert variant="error">{error}</Alert>}

          <Button
            variant="primary"
            onClick={handleImport}
            isLoading={loading}
            disabled={!file || loading}
          >
            Importar
          </Button>
        </div>
      </Card>

      {/* Resultado */}
      {result && (
        <Card>
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Resultado da Importação</h2>

          <div className="flex items-center gap-6 mb-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{result.created_count}</p>
              <p className="text-xs text-gray-500">
                {activeTab === "users" ? "Usuários criados" : "Equipes criadas"}
              </p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-500">{result.errors.length}</p>
              <p className="text-xs text-gray-500">Erros</p>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-700 mb-2">Detalhes dos erros:</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-3 py-2 text-left text-gray-500 font-medium">Linha</th>
                      <th className="px-3 py-2 text-left text-gray-500 font-medium">
                        {activeTab === "users" ? "E-mail" : "Equipe"}
                      </th>
                      <th className="px-3 py-2 text-left text-gray-500 font-medium">Motivo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {result.errors.map((err, i) => (
                      <tr key={i} className="hover:bg-red-50">
                        <td className="px-3 py-2 text-gray-600">{err.row}</td>
                        <td className="px-3 py-2 text-gray-600">{err.identifier || "—"}</td>
                        <td className="px-3 py-2 text-red-600">{err.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.errors.length === 0 && (
            <Alert variant="success">
              Importação concluída com sucesso. Todos os registros foram criados.
            </Alert>
          )}
        </Card>
      )}
    </div>
  );
}

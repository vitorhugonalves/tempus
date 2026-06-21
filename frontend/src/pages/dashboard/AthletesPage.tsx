import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { PlusIcon, ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import { athletesApi } from "../../api/athletes";
import { categoriesApi } from "../../api/categories";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Athlete, AthleteCreate, Category, TshirtSize } from "../../types";

const TSHIRT_SIZES: TshirtSize[] = ["P", "M", "G", "GG", "XG"];

export default function AthletesPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);

  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [filterCat, setFilterCat] = useState<string>("");
  const [search, setSearch] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState<AthleteCreate>({ name: "" });

  useEffect(() => {
    Promise.all([
      athletesApi.list(id).then((r: any) => r.data ?? r),
      categoriesApi.list(id),
    ])
      .then(([a, c]) => { setAthletes(a); setCategories(c); })
      .catch(() => setError("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  }, [id]);

  const filtered = athletes.filter((a) => {
    if (filterCat && String(a.category_id) !== filterCat) return false;
    if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res: any = await athletesApi.create(id, form);
      setAthletes((p) => [...p, res.data ?? res]);
      setForm({ name: "" });
      setShowForm(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao criar atleta");
    }
  }

  async function handleDelete(athleteId: number) {
    if (!window.confirm("Remover este atleta?")) return;
    try {
      await athletesApi.delete(id, athleteId);
      setAthletes((p) => p.filter((a) => a.id !== athleteId));
    } catch {
      setError("Erro ao remover atleta");
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setImportResult(null);
    try {
      const res: any = await athletesApi.importCsv(id, file);
      const data = res.data ?? res;
      setImportResult(
        `${data.created} atleta(s) importado(s) com sucesso.${data.errors.length ? ` ${data.errors.length} erro(s).` : ""}`
      );
      const updated: any = await athletesApi.list(id);
      setAthletes(updated.data ?? updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro na importação");
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Atletas</h1>
        <div className="flex gap-2">
          <div className="flex flex-col items-end gap-1">
            <label className="flex cursor-pointer items-center gap-2 rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
              <ArrowUpTrayIcon className="h-4 w-4" />
              Importar CSV
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="sr-only"
                onChange={handleImport}
              />
            </label>
            <p className="text-xs text-gray-400">
              Formato: <code className="font-mono">nome;categoria;equipe</code> — separador{" "}
              <code className="font-mono">;</code>. Equipe criada automaticamente se não existir.
            </p>
          </div>
          <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
            <PlusIcon className="h-4 w-4" /> Novo Atleta
          </Button>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {importResult && (
        <Alert variant="success">{importResult}</Alert>
      )}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
        >
          <h3 className="font-medium">Novo Atleta</h3>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Nome *"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              required
            />
            <Input
              label="Email"
              type="email"
              value={form.email ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value || undefined }))}
            />
            <Input
              label="Documento (CPF)"
              value={form.document ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, document: e.target.value || undefined }))}
            />
            <Input
              label="Telefone"
              value={form.phone ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value || undefined }))}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700">Categoria</label>
              <select
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                value={form.category_id ?? ""}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    category_id: e.target.value ? Number(e.target.value) : undefined,
                  }))
                }
              >
                <option value="">Sem categoria</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Tamanho de Camiseta</label>
              <select
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                value={form.tshirt_size ?? ""}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    tshirt_size: (e.target.value as TshirtSize) || undefined,
                  }))
                }
              >
                <option value="">—</option>
                {TSHIRT_SIZES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Salvar</Button>
            <Button variant="secondary" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {/* Filtros */}
      <div className="flex gap-3">
        <Input
          placeholder="Buscar por nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          className="rounded-md border-gray-300 text-sm shadow-sm"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categories.map((c) => (
            <option key={c.id} value={String(c.id)}>{c.name}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Nome</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Email</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Documento</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Categoria</th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                  Nenhum atleta encontrado
                </td>
              </tr>
            ) : (
              filtered.map((athlete) => {
                const cat = categories.find((c) => c.id === athlete.category_id);
                return (
                  <tr key={athlete.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{athlete.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{athlete.email ?? "—"}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{athlete.document ?? "—"}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{cat?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(athlete.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Remover
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

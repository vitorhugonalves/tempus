import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { competitionsApi, type CompetitionCreate } from "../api/competitions";
import { useAuthStore } from "../store/auth";
import { Card, CardHeader } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type { Competition } from "../types";

const STATUS_BADGE: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  draft: { label: "Rascunho", variant: "gray" },
  active: { label: "Ativa", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

const INITIAL_FORM: CompetitionCreate = {
  name: "",
  location: "",
  event_date: "",
  modality: "",
  max_athletes: 300,
};

export default function CompetitionsPage() {
  const { user } = useAuthStore();
  const canManage = user?.role === "admin" || user?.role === "operator";

  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CompetitionCreate>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const { data } = await competitionsApi.list();
      setCompetitions(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await competitionsApi.create(form);
      setShowForm(false);
      setForm(INITIAL_FORM);
      await load();
    } catch {
      setError("Erro ao criar competição. Tente novamente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Competições</h1>
          <p className="text-gray-500 text-sm mt-1">Gerencie as competições do sistema</p>
        </div>
        {canManage && (
          <Button
            variant="primary"
            onClick={() => setShowForm(!showForm)}
          >
            <PlusIcon className="h-4 w-4" />
            Nova Competição
          </Button>
        )}
      </div>

      {/* Create form */}
      {showForm && canManage && (
        <Card>
          <CardHeader title="Nova Competição" />
          {error && (
            <div className="mb-4">
              <Alert variant="error">{error}</Alert>
            </div>
          )}
          <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Input
                label="Nome *"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Hyrox São Paulo 2026"
                required
              />
            </div>
            <Input
              label="Local"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="Ex: São Paulo, SP"
            />
            <Input
              label="Modalidade"
              value={form.modality}
              onChange={(e) => setForm({ ...form, modality: e.target.value })}
              placeholder="Ex: Hyrox, CrossFit"
            />
            <Input
              label="Data do Evento"
              type="date"
              value={form.event_date}
              onChange={(e) => setForm({ ...form, event_date: e.target.value })}
            />
            <Input
              label="Máx. Atletas"
              type="number"
              min={1}
              max={300}
              value={form.max_athletes}
              onChange={(e) =>
                setForm({ ...form, max_athletes: Number(e.target.value) })
              }
            />
            <div className="sm:col-span-2 flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowForm(false);
                  setError(null);
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" isLoading={saving}>
                Criar Competição
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Competitions list */}
      <Card padding="none">
        <CardHeader
          title="Lista de Competições"
          description={`${competitions.length} competição(ões) cadastrada(s)`}
          className="px-6 pt-6"
        />
        {loading ? (
          <div className="px-6 pb-8 text-center text-gray-400 text-sm">Carregando...</div>
        ) : competitions.length === 0 ? (
          <div className="px-6 pb-12 text-center text-gray-400 text-sm">
            Nenhuma competição cadastrada ainda.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-gray-100 bg-gray-50">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Nome
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Local
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Modalidade
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Atletas
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {competitions.map((comp) => {
                  const { label, variant } = STATUS_BADGE[comp.status] ?? STATUS_BADGE.draft;
                  return (
                    <tr key={comp.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-gray-900">{comp.name}</td>
                      <td className="px-6 py-4 text-gray-500">{comp.location ?? "—"}</td>
                      <td className="px-6 py-4 text-gray-500">{comp.modality ?? "—"}</td>
                      <td className="px-6 py-4 text-gray-500">{comp.max_athletes}</td>
                      <td className="px-6 py-4">
                        <Badge variant={variant}>{label}</Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Link
                          to={`/ranking/${comp.id}`}
                          className="text-primary-600 hover:text-primary-700 font-medium"
                        >
                          Ranking
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

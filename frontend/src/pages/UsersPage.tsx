import { useEffect, useState } from "react";
import { PlusIcon } from "@heroicons/react/24/outline";
import { usersApi, type UserCreate } from "../api/users";
import { Card, CardHeader } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type { User, UserRole } from "../types";

const ROLE_BADGE: Record<UserRole, { label: string; variant: "blue" | "purple" | "yellow" | "gray" }> = {
  admin: { label: "Admin", variant: "purple" },
  operator: { label: "Operador", variant: "blue" },
  judge: { label: "Juiz", variant: "yellow" },
  competitor: { label: "Competidor", variant: "gray" },
};

const INITIAL_FORM: UserCreate = {
  full_name: "",
  email: "",
  password: "",
  role: "competitor",
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<UserCreate>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const { data } = await usersApi.list();
      setUsers(data);
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
      await usersApi.create(form);
      setShowForm(false);
      setForm(INITIAL_FORM);
      await load();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 409
          ? "E-mail já cadastrado no sistema."
          : "Erro ao criar usuário. Tente novamente."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(user: User) {
    await usersApi.update(user.id, { is_active: !user.is_active });
    await load();
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Usuários</h1>
          <p className="text-gray-500 text-sm mt-1">Gerencie os usuários do sistema</p>
        </div>
        <Button variant="primary" onClick={() => setShowForm(!showForm)}>
          <PlusIcon className="h-4 w-4" />
          Novo Usuário
        </Button>
      </div>

      {/* Create form */}
      {showForm && (
        <Card>
          <CardHeader title="Novo Usuário" />
          {error && (
            <div className="mb-4">
              <Alert variant="error">{error}</Alert>
            </div>
          )}
          <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Input
                label="Nome Completo *"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Ex: João Silva"
                required
              />
            </div>
            <Input
              label="E-mail *"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="joao@email.com"
              required
            />
            <Input
              label="Senha *"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="Mínimo 8 caracteres"
              required
            />
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Perfil *</label>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="competitor">Competidor</option>
                <option value="judge">Juiz</option>
                <option value="operator">Operador</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
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
                Criar Usuário
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Users table */}
      <Card padding="none">
        <CardHeader
          title="Lista de Usuários"
          description={`${users.length} usuário(s) cadastrado(s)`}
          className="px-6 pt-6"
        />
        {loading ? (
          <div className="px-6 pb-8 text-center text-gray-400 text-sm">Carregando...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-gray-100 bg-gray-50">
                  {["Nome", "E-mail", "Perfil", "Status", "Ações"].map((h) => (
                    <th
                      key={h}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((u) => {
                  const { label, variant } = ROLE_BADGE[u.role];
                  return (
                    <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-gray-900">{u.full_name}</td>
                      <td className="px-6 py-4 text-gray-500">{u.email}</td>
                      <td className="px-6 py-4">
                        <Badge variant={variant}>{label}</Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={u.is_active ? "green" : "red"}>
                          {u.is_active ? "Ativo" : "Inativo"}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleActive(u)}
                        >
                          {u.is_active ? "Desativar" : "Ativar"}
                        </Button>
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

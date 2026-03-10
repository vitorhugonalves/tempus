import { useEffect, useState } from "react";
import { EnvelopeIcon, PlusIcon } from "@heroicons/react/24/outline";
import { usersApi, type UserCreate, type UserUpdate } from "../api/users";
import apiClient from "../api/client";
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

const INITIAL_CREATE_FORM: UserCreate = {
  full_name: "",
  email: "",
  password: "",
  role: "competitor",
};

interface EditFormState {
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

function buildEditForm(user: User): EditFormState {
  return {
    full_name: user.full_name,
    email: user.email,
    role: user.role,
    is_active: user.is_active,
  };
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<UserCreate>(INITIAL_CREATE_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Inline edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditFormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Invite form state
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

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

  // --- Create user ---
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      await usersApi.create(createForm);
      setShowCreateForm(false);
      setCreateForm(INITIAL_CREATE_FORM);
      await load();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setCreateError(
        status === 409
          ? "E-mail já cadastrado no sistema."
          : "Erro ao criar usuário. Tente novamente."
      );
    } finally {
      setCreating(false);
    }
  }

  // --- Toggle active (quick action) ---
  async function handleToggleActive(user: User) {
    await usersApi.update(user.id, { is_active: !user.is_active });
    await load();
  }

  // --- Inline edit ---
  function startEdit(user: User) {
    setEditingId(user.id);
    setEditForm(buildEditForm(user));
    setEditError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditForm(null);
    setEditError(null);
  }

  async function handleSaveEdit(userId: number) {
    if (!editForm) return;
    setEditError(null);
    setSaving(true);
    try {
      const payload: UserUpdate = {
        full_name: editForm.full_name,
        email: editForm.email,
        role: editForm.role,
        is_active: editForm.is_active,
      };
      await usersApi.update(userId, payload);
      cancelEdit();
      await load();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setEditError(
        status === 409
          ? "E-mail já utilizado por outro usuário."
          : "Erro ao salvar alterações. Tente novamente."
      );
    } finally {
      setSaving(false);
    }
  }

  // --- Invite competitor ---
  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setInviteSuccess(null);
    setInviting(true);
    try {
      const { data } = await apiClient.post<{ invite_link?: string; message?: string }>(
        "/api/v1/auth/invite",
        { email: inviteEmail }
      );
      const link = data?.invite_link ?? data?.message ?? "Convite enviado com sucesso.";
      setInviteSuccess(link);
      setInviteEmail("");
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setInviteError(
        status === 409
          ? "Este e-mail já está cadastrado no sistema."
          : "Erro ao enviar convite. Tente novamente."
      );
    } finally {
      setInviting(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Usuários</h1>
          <p className="text-gray-500 text-sm mt-1">Gerencie os usuários do sistema</p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            onClick={() => {
              setShowInviteForm(!showInviteForm);
              setInviteError(null);
              setInviteSuccess(null);
              setInviteEmail("");
            }}
          >
            <EnvelopeIcon className="h-4 w-4" />
            Convidar Competidor
          </Button>
          <Button variant="primary" onClick={() => setShowCreateForm(!showCreateForm)}>
            <PlusIcon className="h-4 w-4" />
            Novo Usuário
          </Button>
        </div>
      </div>

      {/* Invite form */}
      {showInviteForm && (
        <Card>
          <CardHeader title="Convidar Competidor" description="Envie um convite por e-mail para que o competidor crie sua conta." />
          {inviteError && (
            <div className="mb-4">
              <Alert variant="error">{inviteError}</Alert>
            </div>
          )}
          {inviteSuccess && (
            <div className="mb-4">
              <Alert variant="success" title="Convite enviado!">
                {inviteSuccess}
              </Alert>
            </div>
          )}
          <form onSubmit={handleSendInvite} className="flex items-end gap-3">
            <div className="flex-1">
              <Input
                label="E-mail do competidor *"
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="competidor@email.com"
                required
              />
            </div>
            <div className="flex gap-3 pb-0.5">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowInviteForm(false);
                  setInviteError(null);
                  setInviteSuccess(null);
                  setInviteEmail("");
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" isLoading={inviting}>
                Enviar Convite
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Create form */}
      {showCreateForm && (
        <Card>
          <CardHeader title="Novo Usuário" />
          {createError && (
            <div className="mb-4">
              <Alert variant="error">{createError}</Alert>
            </div>
          )}
          <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Input
                label="Nome Completo *"
                value={createForm.full_name}
                onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                placeholder="Ex: João Silva"
                required
              />
            </div>
            <Input
              label="E-mail *"
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
              placeholder="joao@email.com"
              required
            />
            <Input
              label="Senha *"
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              placeholder="Mínimo 8 caracteres"
              required
            />
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Perfil *</label>
              <select
                value={createForm.role}
                onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
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
                  setShowCreateForm(false);
                  setCreateError(null);
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" isLoading={creating}>
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
                  const isEditing = editingId === u.id;

                  return (
                    <>
                      {/* Main row */}
                      <tr
                        key={u.id}
                        className={isEditing ? "bg-primary-50" : "hover:bg-gray-50 transition-colors"}
                      >
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
                          <div className="flex items-center gap-2">
                            {isEditing ? (
                              <span className="text-xs text-primary-600 font-medium">Editando...</span>
                            ) : (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => startEdit(u)}
                                >
                                  Editar
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleToggleActive(u)}
                                >
                                  {u.is_active ? "Desativar" : "Ativar"}
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Inline edit row */}
                      {isEditing && editForm && (
                        <tr key={`edit-${u.id}`} className="bg-gray-50">
                          <td colSpan={5} className="px-6 py-4">
                            {editError && (
                              <div className="mb-4">
                                <Alert variant="error">{editError}</Alert>
                              </div>
                            )}
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                              <Input
                                label="Nome Completo"
                                value={editForm.full_name}
                                onChange={(e) =>
                                  setEditForm({ ...editForm, full_name: e.target.value })
                                }
                                placeholder="Nome completo"
                                required
                              />
                              <Input
                                label="E-mail"
                                type="email"
                                value={editForm.email}
                                onChange={(e) =>
                                  setEditForm({ ...editForm, email: e.target.value })
                                }
                                placeholder="email@exemplo.com"
                                required
                              />
                              <div className="flex flex-col gap-1">
                                <label className="text-sm font-medium text-gray-700">Perfil</label>
                                <select
                                  value={editForm.role}
                                  onChange={(e) =>
                                    setEditForm({ ...editForm, role: e.target.value })
                                  }
                                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                >
                                  <option value="competitor">Competidor</option>
                                  <option value="judge">Juiz</option>
                                  <option value="operator">Operador</option>
                                  <option value="admin">Administrador</option>
                                </select>
                              </div>
                              <div className="flex flex-col gap-1">
                                <label className="text-sm font-medium text-gray-700">Status</label>
                                <div className="flex items-center gap-3 py-2">
                                  <button
                                    type="button"
                                    role="switch"
                                    aria-checked={editForm.is_active}
                                    onClick={() =>
                                      setEditForm({ ...editForm, is_active: !editForm.is_active })
                                    }
                                    className={[
                                      "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent",
                                      "transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2",
                                      editForm.is_active ? "bg-primary-600" : "bg-gray-200",
                                    ].join(" ")}
                                  >
                                    <span
                                      className={[
                                        "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0",
                                        "transition duration-200 ease-in-out",
                                        editForm.is_active ? "translate-x-5" : "translate-x-0",
                                      ].join(" ")}
                                    />
                                  </button>
                                  <span className="text-sm text-gray-700">
                                    {editForm.is_active ? "Ativo" : "Inativo"}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-gray-200">
                              <Button type="button" variant="secondary" onClick={cancelEdit}>
                                Cancelar
                              </Button>
                              <Button
                                type="button"
                                variant="primary"
                                isLoading={saving}
                                onClick={() => handleSaveEdit(u.id)}
                              >
                                Salvar Alterações
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
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

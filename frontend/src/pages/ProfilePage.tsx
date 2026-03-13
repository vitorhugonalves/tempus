import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { usersApi } from "../api/users";
import { Card, CardHeader } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, logout, initialize } = useAuthStore();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);
    setSaving(true);
    try {
      await usersApi.updateMe({ full_name: fullName, email });
      await initialize();
      setSaveSuccess("Dados atualizados com sucesso.");
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSaveError(
        status === 409
          ? "E-mail já em uso por outro usuário."
          : detail ?? "Erro ao atualizar dados. Tente novamente."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    try {
      await usersApi.deleteMe();
      await logout();
      navigate("/login", { replace: true });
    } catch {
      alert("Erro ao excluir conta. Tente novamente.");
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Meu Perfil</h1>
        <p className="text-gray-500 text-sm mt-1">Gerencie seus dados pessoais e conta.</p>
      </div>

      {/* Edit profile */}
      <Card>
        <CardHeader title="Dados Pessoais" />
        {saveError && (
          <div className="mb-4">
            <Alert variant="error">{saveError}</Alert>
          </div>
        )}
        {saveSuccess && (
          <div className="mb-4">
            <Alert variant="success">{saveSuccess}</Alert>
          </div>
        )}
        <form onSubmit={handleSave} className="space-y-4">
          <Input
            label="Nome completo"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Seu nome completo"
            required
            minLength={2}
          />
          <Input
            label="E-mail"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="seu@email.com"
            required
          />
          <div className="flex justify-end pt-2">
            <Button type="submit" variant="primary" isLoading={saving}>
              Salvar Alterações
            </Button>
          </div>
        </form>
      </Card>

      {/* Delete account */}
      <Card>
        <CardHeader
          title="Excluir Conta"
          description="Esta ação é permanente e não pode ser desfeita. Todos os seus dados serão removidos."
        />
        {!confirmDelete ? (
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            Excluir minha conta
          </Button>
        ) : (
          <div className="space-y-3">
            <Alert variant="error">
              Tem certeza que deseja excluir sua conta permanentemente? Esta ação não pode ser desfeita.
            </Alert>
            <div className="flex items-center gap-3">
              <Button variant="danger" isLoading={deleting} onClick={handleDeleteAccount}>
                Sim, excluir minha conta
              </Button>
              <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

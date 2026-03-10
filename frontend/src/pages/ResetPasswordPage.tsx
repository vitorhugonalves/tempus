import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import { authApi } from "../api/auth";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Link inválido</h2>
        <Alert variant="error">
          Este link de redefinição é inválido ou expirou. Solicite um novo link.
        </Alert>
        <p className="mt-6 text-center text-sm text-gray-500">
          <Link to="/forgot-password" className="text-primary-600 hover:underline font-medium">
            Solicitar novo link
          </Link>
        </p>
      </>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirm) {
      setError("As senhas não coincidem.");
      return;
    }

    setIsLoading(true);
    try {
      await authApi.resetPassword(token, newPassword);
      navigate("/login", { replace: true, state: { passwordReset: true } });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Token inválido ou expirado. Solicite um novo link.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <h2 className="text-2xl font-bold text-gray-900 mb-1">Redefinir senha</h2>
      <p className="text-sm text-gray-500 mb-6">
        Escolha uma nova senha para sua conta.
      </p>

      {error && (
        <div className="mb-5">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="Nova senha"
          type="password"
          placeholder="Mínimo 8 caracteres"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
          autoFocus
        />

        <Input
          label="Confirmar senha"
          type="password"
          placeholder="Repita a senha"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
        />

        <Button
          type="submit"
          variant="primary"
          size="lg"
          isLoading={isLoading}
          className="w-full mt-2"
        >
          Redefinir senha
        </Button>
      </form>
    </>
  );
}

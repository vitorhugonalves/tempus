import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import { authApi } from "../api/auth";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { initialize } = useAuthStore();

  const token = searchParams.get("token") ?? "";

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Link inválido</h2>
        <Alert variant="error">
          Este link de convite é inválido ou expirou. Solicite um novo convite ao organizador.
        </Alert>
      </>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await authApi.registerViaInvite({ token, full_name: fullName, email, password });
      await initialize();
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao realizar cadastro. Verifique os dados e tente novamente.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <h2 className="text-2xl font-bold text-gray-900 mb-1">Criar conta</h2>
      <p className="text-sm text-gray-500 mb-6">
        Preencha os dados abaixo para concluir seu cadastro.
      </p>

      {error && (
        <div className="mb-5">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="Nome completo"
          type="text"
          placeholder="Seu nome"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          autoFocus
        />

        <Input
          label="E-mail"
          type="email"
          placeholder="seu@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
        />

        <Input
          label="Senha"
          type="password"
          placeholder="Mínimo 8 caracteres"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
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
          Criar conta
        </Button>
      </form>
    </>
  );
}

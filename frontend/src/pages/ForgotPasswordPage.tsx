import { useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import { authApi } from "../api/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await authApi.forgotPassword(email);
      setSubmitted(true);
    } catch {
      setError("Erro ao enviar e-mail. Tente novamente mais tarde.");
    } finally {
      setIsLoading(false);
    }
  }

  if (submitted) {
    return (
      <>
        <h2 className="text-2xl font-bold text-gray-900 mb-4">E-mail enviado</h2>
        <Alert variant="success">
          Se este e-mail estiver cadastrado, você receberá um link para redefinir sua senha em breve.
        </Alert>
        <p className="mt-6 text-center text-sm text-gray-500">
          <Link to="/login" className="text-primary-600 hover:underline font-medium">
            Voltar ao login
          </Link>
        </p>
      </>
    );
  }

  return (
    <>
      <h2 className="text-2xl font-bold text-gray-900 mb-1">Esqueci minha senha</h2>
      <p className="text-sm text-gray-500 mb-6">
        Informe seu e-mail e enviaremos um link para redefinir sua senha.
      </p>

      {error && (
        <div className="mb-5">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="E-mail"
          type="email"
          placeholder="seu@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          autoFocus
        />

        <Button
          type="submit"
          variant="primary"
          size="lg"
          isLoading={isLoading}
          className="w-full mt-2"
        >
          Enviar link de recuperação
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-gray-500">
        <Link to="/login" className="text-primary-600 hover:underline font-medium">
          Voltar ao login
        </Link>
      </p>
    </>
  );
}

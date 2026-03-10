/**
 * Testa que as chamadas da API chegam ao backend via proxy Vite.
 *
 * Estes são testes de integração que requerem o backend em execução
 * em http://127.0.0.1:8000. Execute com:
 *   npx vitest run src/test/proxy.test.ts
 *
 * Em CI/CD sem backend, pule com: SKIP_PROXY_TESTS=true
 */
import { describe, it, expect, beforeAll } from "vitest";

const BACKEND_URL = "http://127.0.0.1:8000";
const PROXY_URL = "http://localhost:5173";

const skipIfNoBackend = (fn: () => Promise<void>) => async () => {
  if (process.env.SKIP_PROXY_TESTS === "true") {
    return;
  }
  await fn();
};

describe("Vite proxy → backend", () => {
  beforeAll(async () => {
    // Verifica se o backend está acessível antes de rodar os testes
    try {
      const res = await fetch(`${BACKEND_URL}/health`);
      if (!res.ok) throw new Error("Backend não está saudável");
    } catch {
      if (process.env.SKIP_PROXY_TESTS !== "true") {
        throw new Error(
          "Backend não está rodando em http://127.0.0.1:8000. " +
            "Inicie o backend ou defina SKIP_PROXY_TESTS=true para pular."
        );
      }
    }
  });

  it(
    "GET /api/v1/auth/me via proxy retorna 401 (sem sessão)",
    skipIfNoBackend(async () => {
      const res = await fetch(`${PROXY_URL}/api/v1/auth/me`);
      expect(res.status).toBe(401);
    })
  );

  it(
    "POST /api/v1/auth/login via proxy retorna 401 para credenciais inválidas",
    skipIfNoBackend(async () => {
      const res = await fetch(`${PROXY_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "naoexiste@example.com", password: "errado" }),
      });
      expect(res.status).toBe(401);
    })
  );

  it(
    "resposta do proxy tem Content-Type JSON (vem do FastAPI, não do Vite)",
    skipIfNoBackend(async () => {
      const res = await fetch(`${PROXY_URL}/api/v1/auth/me`);
      expect(res.headers.get("content-type")).toContain("application/json");
    })
  );

  it(
    "backend direto e via proxy retornam o mesmo status para /api/v1/auth/me",
    skipIfNoBackend(async () => {
      const [direct, proxied] = await Promise.all([
        fetch(`${BACKEND_URL}/api/v1/auth/me`),
        fetch(`${PROXY_URL}/api/v1/auth/me`),
      ]);
      expect(proxied.status).toBe(direct.status);
    })
  );
});

import axios from "axios";

const apiClient = axios.create({
  baseURL: "",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Remove o Content-Type para FormData — o browser seta automaticamente com o boundary correto
apiClient.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

// Rotas públicas que não devem ser redirecionadas para /login ao receber 401
const PUBLIC_PATHS = ["/login", "/reset-password", "/forgot-password", "/register", "/signup", "/ranking", "/wod-leaderboard", "/inscricao"];

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Casamento por segmento de rota (não substring solta) — algumas rotas públicas
    // são aninhadas, ex.: /competitions/:id/inscricao e /competitions/:id/ranking,
    // então checamos igualdade exata, prefixo seguido de "/" ou sufixo do path,
    // nunca uma substring arbitrária no meio (evitaria falso positivo tipo
    // /admin/login-history "contendo" /login).
    const isPublicPath = PUBLIC_PATHS.some((p) => {
      const pathname = window.location.pathname;
      return pathname === p || pathname.startsWith(p + "/") || pathname.endsWith(p);
    });
    if (error.response?.status === 401 && !isPublicPath) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;

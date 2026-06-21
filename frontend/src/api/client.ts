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
const PUBLIC_PATHS = ["/login", "/reset-password", "/forgot-password", "/register", "/signup", "/ranking", "/wod-leaderboard"];

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isPublicPath = PUBLIC_PATHS.some((p) =>
      window.location.pathname.startsWith(p)
    );
    if (error.response?.status === 401 && !isPublicPath) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;

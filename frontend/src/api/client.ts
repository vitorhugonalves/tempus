import axios from "axios";

const apiClient = axios.create({
  baseURL: "",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Rotas públicas que não devem ser redirecionadas para /login ao receber 401
const PUBLIC_PATHS = ["/login", "/reset-password", "/forgot-password", "/register"];

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

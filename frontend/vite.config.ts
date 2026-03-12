import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const LOG_DIR = path.resolve(__dirname, "../logs");
const ACCESS_LOG = path.join(LOG_DIR, "access.log");

function appendProxyError(req: { method?: string; url?: string }, err: Error) {
  const now = new Date()
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d+Z$/, "");
  const method = req.method ?? "-";
  const url = req.url ?? "-";
  const line = `${now} | ERROR    | vite.proxy | "${method} ${url}" PROXY_ERROR: ${err.message}\n`;
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(ACCESS_LOG, line, "utf-8");
  } catch {
    // não bloquear o servidor se o log falhar
  }
  console.error(`[vite.proxy] ${method} ${url} → ${err.message}`);
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("error", (err, req) => {
            appendProxyError(req, err);
          });
        },
      },
      "/ws": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },
  },
});

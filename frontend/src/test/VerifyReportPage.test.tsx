import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it, vi, beforeEach } from "vitest";
import VerifyReportPage from "../pages/VerifyReportPage";
import { reportsApi } from "../api/reports";
import type { ReportVerification } from "../types";

vi.mock("../api/reports", () => ({
  reportsApi: {
    verifyByCode: vi.fn(),
    verifyByFile: vi.fn(),
    originalPdfUrl: (code: string) => `/api/v1/reports/verify/${code}/pdf`,
  },
}));

const valid: ReportVerification = {
  status: "valid",
  verification_code: "ABC",
  report_type: "ranking",
  competition_name: "Hyrox Floripa",
  category_name: null,
  issued_at: "2026-10-22T15:30:00Z",
  issued_by_role: "admin",
  sha256: "a".repeat(64),
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/verificar" element={<VerifyReportPage />} />
        <Route path="/verificar/:code" element={<VerifyReportPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function httpError(status: number): AxiosError {
  return new AxiosError("http", "ERR", undefined, undefined, {
    status,
    statusText: "",
    data: {},
    headers: {},
    config: { headers: new AxiosHeaders() },
  });
}

describe("VerifyReportPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra documento autêntico com link do original", async () => {
    vi.mocked(reportsApi.verifyByCode).mockResolvedValue(valid);
    renderAt("/verificar/ABC");
    expect(await screen.findByText("Documento autêntico")).toBeInTheDocument();
    expect(screen.getByText("Hyrox Floripa")).toBeInTheDocument();
    expect(screen.getByText(/22\/10\/2026 12:30/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /baixar original/i })).toHaveAttribute(
      "href",
      "/api/v1/reports/verify/ABC/pdf",
    );
  });

  it("alerta documento adulterado sem oferecer download", async () => {
    vi.mocked(reportsApi.verifyByCode).mockResolvedValue({ ...valid, status: "tampered" });
    renderAt("/verificar/ABC");
    expect(await screen.findByText("Documento adulterado")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /baixar original/i })).not.toBeInTheDocument();
  });

  it("informa código não encontrado", async () => {
    vi.mocked(reportsApi.verifyByCode).mockRejectedValue(httpError(404));
    renderAt("/verificar/XYZ");
    await waitFor(() =>
      expect(screen.getByText(/não corresponde a nenhum relatório/i)).toBeInTheDocument(),
    );
  });

  it("pede para aguardar quando o limite de consultas é atingido", async () => {
    vi.mocked(reportsApi.verifyByCode).mockRejectedValue(httpError(429));
    renderAt("/verificar/ABC");
    expect(await screen.findByText(/muitas verificações/i)).toBeInTheDocument();
  });

  it("sem código mostra campo de código e upload", () => {
    renderAt("/verificar");
    expect(screen.getByLabelText(/código de verificação/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/arquivo pdf/i)).toBeInTheDocument();
  });
});

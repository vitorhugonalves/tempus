import apiClient from "./client";
import type { ReportVerification } from "../types";

export const reportsApi = {
  verifyByCode: (code: string) =>
    apiClient
      .get<ReportVerification>(`/api/v1/reports/verify/${encodeURIComponent(code)}`)
      .then((r) => r.data),

  verifyByFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<ReportVerification>("/api/v1/reports/verify", form).then((r) => r.data);
  },

  originalPdfUrl: (code: string) => `/api/v1/reports/verify/${encodeURIComponent(code)}/pdf`,
};

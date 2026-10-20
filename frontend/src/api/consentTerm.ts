import apiClient from "./client";

export interface ConsentTermMeta {
  has_term: boolean;
  file_name: string | null;
  uploaded_at: string | null;
}

export const consentTermApi = {
  get: (competitionId: number) =>
    apiClient
      .get<ConsentTermMeta>(`/api/v1/competitions/${competitionId}/consent-term`)
      .then((r) => r.data),

  upload: (competitionId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient
      .post<ConsentTermMeta>(
        `/api/v1/competitions/${competitionId}/consent-term`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      )
      .then((r) => r.data);
  },

  delete: (competitionId: number) =>
    apiClient.delete(`/api/v1/competitions/${competitionId}/consent-term`),

  fileUrl: (competitionId: number) =>
    `/api/v1/competitions/${competitionId}/consent-term/file`,
};

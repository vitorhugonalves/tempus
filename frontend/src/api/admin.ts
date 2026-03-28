import apiClient from "./client";

export interface BoxSettingsData {
  id: number;
  name: string;
  address: string | null;
  website: string | null;
  instagram: string | null;
  has_logo: boolean;
  created_at: string;
  updated_at: string;
}

export interface BoxSettingsUpdate {
  name?: string;
  address?: string | null;
  website?: string | null;
  instagram?: string | null;
}

export interface BulkError {
  row: number;
  identifier: string;
  reason: string;
}

export interface BulkImportResult {
  created_count: number;
  errors: BulkError[];
}

export const adminApi = {
  getSettings: () => apiClient.get<BoxSettingsData>("/api/v1/admin/settings"),

  updateSettings: (data: BoxSettingsUpdate) =>
    apiClient.put<BoxSettingsData>("/api/v1/admin/settings", data),

  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<BoxSettingsData>("/api/v1/admin/settings/logo", form);
  },

  getLogoUrl: () => "/api/v1/admin/settings/logo",

  bulkImportUsers: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<BulkImportResult>("/api/v1/admin/bulk/users", form);
  },

  bulkImportTeams: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<BulkImportResult>("/api/v1/admin/bulk/teams", form);
  },

  bulkImportHeats: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<BulkImportResult>("/api/v1/admin/bulk/heats", form);
  },
};

import apiClient from "./client";
import type { Modality } from "../types";

export interface ModalityCreate {
  name: string;
  description?: string;
  default_duration_seconds?: number;
}

export interface ModalityUpdate {
  name?: string;
  description?: string;
  default_duration_seconds?: number;
}

export const modalitiesApi = {
  list: () =>
    apiClient.get<Modality[]>("/api/v1/modalities").then((r) => r.data),

  get: (id: number) =>
    apiClient.get<Modality>(`/api/v1/modalities/${id}`).then((r) => r.data),

  create: (data: ModalityCreate) =>
    apiClient.post<Modality>("/api/v1/modalities", data),

  update: (id: number, data: ModalityUpdate) =>
    apiClient.patch<Modality>(`/api/v1/modalities/${id}`, data),

  delete: (id: number) =>
    apiClient.delete(`/api/v1/modalities/${id}`),
};

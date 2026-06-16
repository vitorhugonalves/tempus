import apiClient from "./client";
import type { CepResult } from "../types";

export const cepApi = {
  lookup: (cep: string) =>
    apiClient.get<CepResult>(`/api/v1/cep/${cep.replace(/\D/g, "")}`),
};

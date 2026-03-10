import { create } from "zustand";
import { authApi } from "../api/auth";
import type { LoginResponse } from "../types";

interface AuthState {
  user: LoginResponse | null;
  isLoading: boolean;
  isInitialized: boolean;
  initialize: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  isLoading: false,
  isInitialized: false,

  initialize: async () => {
    set({ isLoading: true });
    try {
      const { data } = await authApi.me();
      set({ user: data });
    } catch {
      set({ user: null });
    } finally {
      set({ isLoading: false, isInitialized: true });
    }
  },

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const { data } = await authApi.login({ email, password });
      set({ user: data });
    } finally {
      set({ isLoading: false });
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } finally {
      set({ user: null });
    }
  },
}));

import { api } from "@/lib/api";

export type User = {
  id: number;
  username: string;
  role: "admin" | "editor" | "viewer";
};

const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

export const login = async (username: string, password: string) => {
  const response = await api.post("/auth/login", { username, password });
  const { access_token, user } = response.data;
  localStorage.setItem(TOKEN_KEY, access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user as User;
};

export const logout = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = "/login";
};

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);

export const getCurrentUser = (): User | null => {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
};

export const isAuthenticated = (): boolean => !!getToken();

export const hasRole = (...roles: string[]): boolean => {
  const user = getCurrentUser();
  return !!user && roles.includes(user.role);
};

export const canEdit = (): boolean => hasRole("admin", "editor");
export const isAdmin = (): boolean => hasRole("admin");
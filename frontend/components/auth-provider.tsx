"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";

import { ApiError, getCurrentUser, login, logout, register, User } from "../lib/api";


type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  loginWithPassword: (payload: { email: string; password: string }) => Promise<User>;
  registerWithPassword: (payload: { email: string; password: string; display_name: string }) => Promise<User>;
  logoutUser: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
};


const AuthContext = createContext<AuthContextValue | null>(null);


/**
 * 统一管理登录用户、初始化鉴权检查和登录/退出行为。
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function refreshUser() {
    try {
      const result = await getCurrentUser();
      setUser(result.user);
      return result.user;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        return null;
      }
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  async function loginWithPassword(payload: { email: string; password: string }) {
    const result = await login(payload);
    setUser(result.user);
    return result.user;
  }

  async function registerWithPassword(payload: { email: string; password: string; display_name: string }) {
    const result = await register(payload);
    setUser(result.user);
    return result.user;
  }

  async function logoutUser() {
    await logout();
    setUser(null);
  }

  useEffect(() => {
    void refreshUser();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        loginWithPassword,
        registerWithPassword,
        logoutUser,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

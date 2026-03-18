"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";

import { createSession, getSessions, SessionSummary } from "../lib/api";
import { useAuth } from "./auth-provider";


type WorkspaceContextValue = {
  sessions: SessionSummary[];
  isLoading: boolean;
  refreshSessions: () => Promise<SessionSummary[]>;
  createChatSession: () => Promise<SessionSummary>;
};


const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);


/**
 * 管理当前登录用户的会话列表。
 */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, isLoading: authLoading } = useAuth();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  async function refreshSessions() {
    if (!user) {
      setSessions([]);
      setIsLoading(false);
      return [];
    }

    try {
      const result = await getSessions();
      setSessions(result);
      return result;
    } finally {
      setIsLoading(false);
    }
  }

  async function createChatSession() {
    const session = await createSession();
    setSessions((current) => [session, ...current.filter((item) => item.session_id !== session.session_id)]);
    return session;
  }

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!user) {
      setSessions([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    void refreshSessions().catch(() => {
      setSessions([]);
    });
  }, [user, authLoading]);

  return (
    <WorkspaceContext.Provider
      value={{
        sessions,
        isLoading,
        refreshSessions,
        createChatSession,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}


export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return context;
}

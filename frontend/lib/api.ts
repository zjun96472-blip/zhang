/**
 * 前端统一的 API 调用封装。
 *
 * 所有请求都固定带上 credentials，让浏览器自动携带后端签发的 HttpOnly Cookie。
 */

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type User = {
  id: string;
  email: string;
  display_name: string;
};

export type AuthEnvelope = {
  user: User;
};

export type Citation = {
  id: string;
  source: string;
  doc_type: string;
  category: string;
  score?: number | null;
};

export type ChatResponse = {
  session_id: string;
  reply: string;
  intent: string;
  citations: Citation[];
  used_tools: string[];
  action: string;
  memory_source: string;
  needs_handoff: boolean;
  handoff_ticket_id?: string | null;
};

export type Ticket = {
  ticket_no: string;
  session_id: string;
  user_id: string;
  reason: string;
  status: string;
  summary: string;
  created_at: string;
};

export type SessionMessage = {
  role: string;
  content: string;
  intent?: string | null;
  citations: Citation[];
  tool_calls: string[];
  created_at: string;
};

export type SessionSnapshot = {
  intent?: string | null;
  memory_source: string;
  state: Record<string, unknown>;
  created_at: string;
};

export type SessionSummary = {
  session_id: string;
  title: string;
  current_intent?: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionPayload = {
  session_id: string;
  user_id: string;
  title: string;
  current_intent?: string | null;
  messages: SessionMessage[];
  snapshots: SessionSnapshot[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) {
        message = data.detail;
      }
    } catch {
      message = response.statusText || message;
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function register(payload: { email: string; password: string; display_name: string }) {
  /** 注册并写入登录 Cookie。 */
  return apiFetch<AuthEnvelope>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: { email: string; password: string }) {
  /** 登录并写入登录 Cookie。 */
  return apiFetch<AuthEnvelope>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout() {
  /** 退出登录并清理后端 Cookie。 */
  return apiFetch<void>("/api/auth/logout", {
    method: "POST",
  });
}

export function getCurrentUser() {
  /** 获取当前登录用户。 */
  return apiFetch<AuthEnvelope>("/api/auth/me");
}

export function postChat(payload: { session_id?: string; message: string }) {
  /** 发送一轮聊天消息。 */
  return apiFetch<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSessions() {
  /** 获取当前用户的会话列表。 */
  return apiFetch<SessionSummary[]>("/api/sessions");
}

export function createSession() {
  /** 创建一个空会话，供“新对话”使用。 */
  return apiFetch<SessionSummary>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getTickets() {
  /** 获取当前用户的人工工单列表。 */
  return apiFetch<Ticket[]>("/api/tickets");
}

export function getSession(sessionId: string) {
  /** 获取某个会话的消息历史和状态快照。 */
  return apiFetch<SessionPayload>(`/api/sessions/${sessionId}`);
}

export function rebuildMemory(sessionId: string) {
  /** 手动触发 Redis 记忆重建，用于演示 MySQL 回放能力。 */
  return apiFetch<{
    session_id: string;
    memory_source: string;
    summary: string;
    slots: Record<string, string>;
    intent?: string | null;
  }>(`/api/memory/rebuild/${sessionId}`, {
    method: "POST",
  });
}

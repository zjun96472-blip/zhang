"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "./auth-provider";
import { useWorkspace } from "./workspace-provider";


/**
 * 登录后的主应用壳子。
 *
 * 左侧提供 GPT 风格的会话栏和导航，右侧展示当前页面内容。
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { user, isLoading, logoutUser } = useAuth();
  const { sessions, isLoading: sessionsLoading, createChatSession } = useWorkspace();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/auth");
    }
  }, [isLoading, user, router]);

  async function handleNewChat() {
    const session = await createChatSession();
    setSidebarOpen(false);
    router.push(`/?session=${session.session_id}`);
  }

  async function handleLogout() {
    await logoutUser();
    router.replace("/auth");
  }

  if (isLoading || !user) {
    return (
      <div className="shell-loading">
        <div className="shell-loading-card">
          <span className="panel-kicker">ShopMate</span>
          <h1>正在恢复登录状态</h1>
          <p>我们在读取当前用户与会话列表，请稍候。</p>
        </div>
      </div>
    );
  }

  const activeSessionId = pathname === "/" ? searchParams.get("session") : null;

  return (
    <div className="product-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand-lockup">
            <div className="brand-mark">S</div>
            <div>
              <p className="brand-title">ShopMate</p>
              <p className="brand-subtitle">Customer Agent</p>
            </div>
          </div>
          <button type="button" className="icon-button mobile-only" onClick={() => setSidebarOpen(false)}>
            关闭
          </button>
        </div>

        <button type="button" className="primary-sidebar-button" onClick={handleNewChat}>
          + 新建对话
        </button>

        <nav className="sidebar-nav">
          <Link href="/" className={pathname === "/" ? "active" : ""} onClick={() => setSidebarOpen(false)}>
            聊天
          </Link>
          <Link href="/tickets" className={pathname === "/tickets" ? "active" : ""} onClick={() => setSidebarOpen(false)}>
            工单
          </Link>
          <Link href="/debug" className={pathname === "/debug" ? "active" : ""} onClick={() => setSidebarOpen(false)}>
            调试
          </Link>
        </nav>

        <section className="history-panel">
          <div className="history-header">
            <span>最近对话</span>
          </div>
          <div className="history-list">
            {sessionsLoading ? <p className="history-empty">会话列表加载中...</p> : null}
            {!sessionsLoading && sessions.length === 0 ? (
              <p className="history-empty">还没有历史对话，点击上方按钮开始。</p>
            ) : null}
            {sessions.map((session) => (
              <Link
                key={session.session_id}
                href={`/?session=${session.session_id}`}
                className={activeSessionId === session.session_id ? "history-item active" : "history-item"}
                onClick={() => setSidebarOpen(false)}
              >
                <span className="history-title">{session.title}</span>
                <span className="history-meta">{session.current_intent ?? "general"}</span>
              </Link>
            ))}
          </div>
        </section>

        <div className="sidebar-user">
          <div>
            <strong>{user.display_name}</strong>
            <p>{user.email}</p>
          </div>
          <button type="button" className="ghost-sidebar-button" onClick={handleLogout}>
            退出
          </button>
        </div>
      </aside>

      <div className="shell-main">
        <header className="topbar">
          <button type="button" className="icon-button mobile-only" onClick={() => setSidebarOpen(true)}>
            菜单
          </button>
          <div>
            <span className="topbar-kicker">ShopMate Demo</span>
            <h1>{pathname === "/" ? "聊天" : pathname === "/tickets" ? "工单" : "调试"}</h1>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}

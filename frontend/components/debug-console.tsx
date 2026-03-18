"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";

import { getSession, rebuildMemory, SessionPayload } from "../lib/api";
import { useWorkspace } from "./workspace-provider";


/**
 * 会话调试面板。
 *
 * 这个页面主要用于展示“Redis 短期记忆 + MySQL 长期回放”的效果。
 */
export function DebugConsole() {
  const { sessions } = useWorkspace();
  const [sessionId, setSessionId] = useState("");
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [rebuildResult, setRebuildResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!sessionId && sessions.length > 0) {
      setSessionId(sessions[0].session_id);
    }
  }, [sessionId, sessions]);

  function handleLoad(event: FormEvent<HTMLFormElement>) {
    /** 加载完整会话详情。 */
    event.preventDefault();
    if (!sessionId.trim()) {
      return;
    }
    setError("");
    startTransition(async () => {
      try {
        const data = await getSession(sessionId.trim());
        setSession(data);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "加载失败");
      }
    });
  }

  function handleRebuild() {
    /** 手动触发 Redis 记忆重建。 */
    if (!sessionId.trim()) {
      return;
    }
    setError("");
    startTransition(async () => {
      try {
        const data = await rebuildMemory(sessionId.trim());
        setRebuildResult(data);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "重建失败");
      }
    });
  }

  return (
    <section className="utility-page">
      <div className="utility-header">
        <span className="panel-kicker">Debug</span>
        <h2>会话与记忆回放</h2>
      </div>

      <div className="utility-card">
        <form className="stack-form" onSubmit={handleLoad}>
          <label className="field">
            <span>选择会话</span>
            <select value={sessionId} onChange={(event) => setSessionId(event.target.value)}>
              <option value="">请选择会话</option>
              {sessions.map((item) => (
                <option key={item.session_id} value={item.session_id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <div className="inline-actions">
            <button type="submit" disabled={isPending}>
              查看会话
            </button>
            <button type="button" className="secondary" disabled={isPending} onClick={handleRebuild}>
              重建 Redis 记忆
            </button>
          </div>
        </form>

        {error ? <p className="error-text">{error}</p> : null}
        {rebuildResult ? (
          <div className="code-card">
            <h3>重建结果</h3>
            <pre>{JSON.stringify(rebuildResult, null, 2)}</pre>
          </div>
        ) : null}
      </div>

      {session ? (
        <div className="utility-grid">
          <div className="code-card">
            <h3>消息历史</h3>
            <pre>{JSON.stringify(session.messages, null, 2)}</pre>
          </div>
          <div className="code-card">
            <h3>状态快照</h3>
            <pre>{JSON.stringify(session.snapshots, null, 2)}</pre>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <p>选择一个属于当前用户的会话后，可以查看 MySQL 历史消息与 Redis 回放结果。</p>
        </div>
      )}
    </section>
  );
}

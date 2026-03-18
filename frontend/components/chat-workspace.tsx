"use client";

import { FormEvent, useEffect, useRef, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ChatResponse, getSession, postChat } from "../lib/api";
import { useWorkspace } from "./workspace-provider";


type Message = {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  meta?: {
    intent?: string | null;
    citations: ChatResponse["citations"];
    used_tools: string[];
    memory_source?: string;
    needs_handoff?: boolean;
  };
};


const EXAMPLES = [
  "AeroFit 智能运动耳机适合跑步吗？",
  "帮我查一下 ORD-10002 现在到哪了",
  "订单 ORD-10003 还能 7 天无理由退货吗？",
  "这个订单太离谱了，我要投诉并申请补偿",
];


/**
 * 主聊天工作区。
 *
 * 行为上参考 GPT：
 * 1. 左栏切换会话
 * 2. 中间展示消息
 * 3. 空会话时显示欢迎态
 * 4. 已有消息时把输入框固定到底部
 */
export function ChatWorkspace() {
  const { sessions, refreshSessions, createChatSession } = useWorkspace();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [isPending, startTransition] = useTransition();
  const messageStreamRef = useRef<HTMLDivElement | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const skipSessionLoadRef = useRef<string | null>(null);
  const scrollIntentRef = useRef<"top" | "bottom" | null>(null);

  const activeSessionId = searchParams.get("session");
  const activeSession = sessions.find((item) => item.session_id === activeSessionId) ?? null;

  useEffect(() => {
    const stream = messageStreamRef.current;
    const intent = scrollIntentRef.current;
    if (!stream || !intent) {
      return;
    }

    const rafId = window.requestAnimationFrame(() => {
      if (intent === "top") {
        stream.scrollTo({ top: 0, behavior: "auto" });
      } else {
        messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
      }
      scrollIntentRef.current = null;
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [messages, isLoadingSession]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }

    if (skipSessionLoadRef.current === activeSessionId) {
      skipSessionLoadRef.current = null;
      return;
    }

    setIsLoadingSession(true);
    setError("");
    setMessages([]);
    scrollIntentRef.current = "top";
    void getSession(activeSessionId)
      .then((session) => {
        setMessages(
          session.messages.map((item) => ({
            role: item.role === "assistant" ? "assistant" : "user",
            content: item.content,
            createdAt: item.created_at,
            meta:
              item.role === "assistant"
                ? {
                    intent: item.intent,
                    citations: item.citations,
                    used_tools: item.tool_calls,
                  }
                : undefined,
          })),
        );
      })
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : "加载会话失败");
      })
      .finally(() => {
        setIsLoadingSession(false);
      });
  }, [activeSessionId]);

  async function ensureSession() {
    if (activeSessionId) {
      return activeSessionId;
    }

    const session = await createChatSession();
    skipSessionLoadRef.current = session.session_id;
    router.replace(`/?session=${session.session_id}`);
    return session.session_id;
  }

  function sendMessage(message: string) {
    setError("");
    scrollIntentRef.current = "bottom";
    setMessages((current) => [...current, { role: "user", content: message }]);

    startTransition(async () => {
      try {
        const sessionId = await ensureSession();
        const result = await postChat({
          session_id: sessionId,
          message,
        });
        scrollIntentRef.current = "bottom";
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: result.reply,
            meta: {
              intent: result.intent,
              citations: result.citations,
              used_tools: result.used_tools,
              memory_source: result.memory_source,
              needs_handoff: result.needs_handoff,
            },
          },
        ]);
        setInput("");
        await refreshSessions();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "请求失败");
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) {
      return;
    }
    sendMessage(trimmed);
  }

  const showWelcome = !activeSessionId && messages.length === 0;

  return (
    <section className="chat-surface">
      <header className="chat-header">
        <div>
          <span className="panel-kicker">Chat</span>
          <h2>{activeSession?.title ?? "新的客服对话"}</h2>
        </div>
        <div className="chat-header-meta">
          {activeSession ? <span>会话：{activeSession.session_id.slice(0, 8)}</span> : <span>尚未创建会话</span>}
        </div>
      </header>

      <div className={`conversation-stage ${showWelcome ? "welcome" : ""}`}>
        {showWelcome ? (
          <div className="welcome-panel">
            <h3>有什么可以帮忙的？</h3>
            <p>你可以问商品信息、物流状态、退款条件，也可以直接触发投诉转人工场景。</p>
            <div className="welcome-examples">
              {EXAMPLES.map((example) => (
                <button key={example} type="button" className="example-card" onClick={() => setInput(example)}>
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {!showWelcome ? (
          <div className="message-stream" ref={messageStreamRef}>
            {isLoadingSession ? (
              <div className="empty-state">
                <p>正在加载这段会话...</p>
              </div>
            ) : null}
            {!isLoadingSession && messages.length === 0 ? (
              <div className="empty-state">
                <p>这个会话还没有消息，发出第一条问题后，系统会自动开始记录上下文。</p>
              </div>
            ) : null}
            {!isLoadingSession
              ? messages.map((message, index) => (
                  <article key={`${message.role}-${index}`} className={`chat-row ${message.role}`}>
                    <div className={`chat-bubble ${message.role}`}>
                      <div className="chat-bubble-meta">
                        <span>{message.role === "user" ? "你" : "ShopMate"}</span>
                        {message.meta?.intent ? <span>{message.meta.intent}</span> : null}
                      </div>
                      <p>{message.content}</p>

                      {message.meta ? (
                        <div className="assistant-meta">
                          <div className="assistant-tags">
                            {message.meta.memory_source ? (
                              <span className="assistant-tag">记忆来源: {message.meta.memory_source}</span>
                            ) : null}
                            {message.meta.used_tools.map((tool) => (
                              <span className="assistant-tag" key={tool}>
                                {tool}
                              </span>
                            ))}
                            {message.meta.needs_handoff ? <span className="assistant-tag alert">已转人工</span> : null}
                          </div>
                          {message.meta.citations.length > 0 ? (
                            <div className="assistant-citations">
                              <h4>引用来源</h4>
                              <ul>
                                {message.meta.citations.map((citation) => (
                                  <li key={citation.id}>
                                    <strong>{citation.source}</strong>
                                    <span>{citation.doc_type}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </article>
                ))
              : null}
            {isPending ? (
              <article className="chat-row assistant">
                <div className="chat-bubble assistant typing-bubble">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </article>
            ) : null}
            <div ref={messageEndRef} />
          </div>
        ) : null}

        <form className={`composer-card ${showWelcome ? "centered" : ""}`} onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            rows={showWelcome ? 3 : 2}
            placeholder="发送商品问题、物流问题或售后问题"
          />
          <div className="composer-bar">
            <span className="composer-status">
              {isPending
                ? "Agent 正在分析你的问题..."
                : activeSession
                  ? `当前会话标题：${activeSession.title}`
                  : "发送后将自动创建新会话"}
            </span>
            <button type="submit" disabled={isPending}>
              {isPending ? "处理中..." : "发送"}
            </button>
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </form>
      </div>
    </section>
  );
}

"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "./auth-provider";


type Mode = "login" | "register";


/**
 * 登录 / 注册单页。
 */
export function AuthScreen() {
  const { user, isLoading, loginWithPassword, registerWithPassword } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [displayName, setDisplayName] = useState("张俊");
  const [email, setEmail] = useState("demo@shopmate.local");
  const [password, setPassword] = useState("demo123456");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/");
    }
  }, [isLoading, user, router]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        if (mode === "login") {
          await loginWithPassword({ email, password });
        } else {
          await registerWithPassword({ email, password, display_name: displayName });
        }
        router.replace("/");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "请求失败");
      }
    });
  }

  return (
    <div className="auth-page">
      <section className="auth-card">
        <div className="auth-copy">
          <span className="panel-kicker">ShopMate</span>
          <h1>登录后开始你的客服 Agent 演示</h1>
          <p>
            现在的界面已经切成真实产品形态：用户登录后自动识别身份，新对话自动生成会话，聊天、工单和调试数据都会按当前用户隔离。
          </p>
          <div className="auth-demo-box">
            <strong>演示账号</strong>
            <p>账号：demo@shopmate.local</p>
            <p>密码：demo123456</p>
          </div>
        </div>

        <div className="auth-form-panel">
          <div className="auth-tabs">
            <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
              登录
            </button>
            <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>
              注册
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "register" ? (
              <label className="field">
                <span>显示名称</span>
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
              </label>
            ) : null}

            <label className="field">
              <span>邮箱</span>
              <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
            </label>

            <label className="field">
              <span>密码</span>
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
            </label>

            <button type="submit" className="auth-submit" disabled={isPending}>
              {isPending ? "提交中..." : mode === "login" ? "登录" : "注册并进入"}
            </button>
            {error ? <p className="error-text">{error}</p> : null}
          </form>
        </div>
      </section>
    </div>
  );
}

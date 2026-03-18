import type { Metadata } from "next";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import { Suspense } from "react";

import { AuthProvider } from "../components/auth-provider";
import { ShellBoundary } from "../components/shell-boundary";
import { WorkspaceProvider } from "../components/workspace-provider";
import "./globals.css";


// 标题字体强调展示感，适合 Demo 首页的视觉氛围。
const headingFont = Space_Grotesk({
  variable: "--font-heading",
  subsets: ["latin"],
});

// 正文字体保证长文本阅读舒适。
const bodyFont = IBM_Plex_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "ShopMate Demo",
  description: "E-commerce support agent demo powered by LangGraph and Milvus.",
};


export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  /** 全局布局负责挂载字体、登录态和会话上下文。 */
  return (
    <html lang="zh-CN">
      <body className={`${headingFont.variable} ${bodyFont.variable}`}>
        <AuthProvider>
          <WorkspaceProvider>
            <Suspense fallback={<div className="shell-loading" />}>
              <ShellBoundary>{children}</ShellBoundary>
            </Suspense>
          </WorkspaceProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

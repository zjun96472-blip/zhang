"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { AppShell } from "./app-shell";


/**
 * 认证页不套主应用壳子，其余页面统一进入带侧边栏的产品布局。
 */
export function ShellBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith("/auth")) {
    return <>{children}</>;
  }
  return <AppShell>{children}</AppShell>;
}

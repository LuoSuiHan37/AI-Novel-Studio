import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 小说工作室",
  description: "AI + 人工协作的英文长篇网文生产系统",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

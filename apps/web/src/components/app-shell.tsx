"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ProjectSidebar } from "@/components/project-sidebar";
import { extractProjectId } from "@/lib/nav";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const projectId = extractProjectId(pathname);
  const isChapterEditor = /^\/projects\/[^/]+\/chapters\/[^/]+$/.test(pathname);
  const [project, setProject] = useState<Project | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    api<Project>(`/projects/${projectId}`).then(setProject).catch(() => setProject(null));
  }, [projectId, pathname]);

  if (isChapterEditor || !projectId) return <div className="min-h-dvh bg-[var(--workspace-bg)] text-foreground"><main className="min-h-dvh min-w-0 px-4 py-16 sm:px-6 md:px-8 md:py-10 xl:px-12">{children}</main></div>;
  return <div className="min-h-dvh bg-[var(--workspace-bg)] text-foreground"><button type="button" aria-label="打开导航" className="fixed left-4 top-4 z-50 flex size-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm md:hidden" onClick={() => setMobileOpen(true)}><Menu className="size-5" /></button><div className={cn("fixed inset-0 z-40 bg-slate-950/20 transition-opacity md:hidden", mobileOpen ? "opacity-100" : "pointer-events-none opacity-0")} onClick={() => setMobileOpen(false)} aria-hidden="true" /><div className={cn("fixed inset-y-0 left-0 z-50 transition-transform duration-200 md:hidden", mobileOpen ? "translate-x-0" : "-translate-x-full")}><ProjectSidebar projectId={projectId} project={project} pathname={pathname} mobile onClose={() => setMobileOpen(false)} /></div><div className="fixed inset-y-0 left-0 z-30 hidden md:block"><ProjectSidebar projectId={projectId} project={project} pathname={pathname} /></div><main className="min-h-dvh min-w-0 px-4 py-16 sm:px-6 md:ml-[220px] md:px-8 md:py-0 xl:px-10">{children}</main></div>;
}

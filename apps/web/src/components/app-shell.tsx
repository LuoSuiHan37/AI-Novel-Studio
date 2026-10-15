"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, ChevronDown, FileText, House, Layers3, Library, Menu, Settings2, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { extractProjectId, getGlobalNav, getProjectNavGroups, isNavActive, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Chapter, Project } from "@/lib/types";

const globalIcons: Record<string, LucideIcon> = { "/": House, "/projects": Library, "/research": Layers3, "/settings": Settings2 };

function NavLink({ item, pathname, onNavigate, icon: Icon }: { item: NavItem; pathname: string; onNavigate?: () => void; icon?: LucideIcon }) {
  const active = isNavActive(pathname, item.href);
  return (
    <Link href={item.href} aria-current={active ? "page" : undefined} onClick={onNavigate} className={cn("group flex min-h-11 w-full items-center gap-3 rounded-xl px-3.5 text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50", active ? "bg-primary/10 text-primary shadow-[inset_3px_0_0_var(--primary)]" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950")}>
      {Icon ? <Icon aria-hidden="true" className="size-[19px]" strokeWidth={1.8} /> : null}
      <span>{item.label}</span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isChapterEditor = /^\/projects\/[^/]+\/chapters\/[^/]+$/.test(pathname);
  const projectId = extractProjectId(pathname);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const groups = projectId ? getProjectNavGroups(projectId) : [];

  useEffect(() => {
    if (!projectId) return;
    Promise.all([api<Project>(`/projects/${projectId}`), api<Chapter[]>(`/projects/${projectId}/chapters`)]).then(([loadedProject, loadedChapters]) => { setProject(loadedProject); setChapters(loadedChapters); }).catch(() => { setProject(null); setChapters([]); });
  }, [projectId, pathname]);

  const sidebar = (
    <aside className="flex h-full w-[220px] flex-col border-r border-slate-200/80 bg-white/95 text-slate-900 shadow-[8px_0_24px_rgba(15,23,42,0.03)] backdrop-blur">
      <div className="flex h-[92px] items-center border-b border-slate-100 px-6">
        <Link href="/" className="flex items-center gap-3" onClick={() => setMobileOpen(false)}>
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><BookOpen aria-hidden="true" className="size-6" strokeWidth={1.8} /></span>
          <span className="font-serif text-[17px] font-semibold tracking-tight">AI 小说工作室</span>
        </Link>
      </div>
      <nav aria-label="主导航" className="flex flex-1 flex-col gap-1 overflow-y-auto px-4 py-6">
        <div className="space-y-1">
          {getGlobalNav().filter((item) => item.href !== "/settings").map((item) => <NavLink key={item.href} item={item} pathname={pathname} onNavigate={() => setMobileOpen(false)} icon={globalIcons[item.href]} />)}
        </div>
        {projectId ? (
          <div className="mt-5 border-y border-slate-100 py-4">
            <p className="mb-2 truncate px-3 text-xs font-semibold text-slate-500" title={project?.title || "当前小说"}>{project?.title || "当前小说"}</p>
            <NavLink item={{ href: `/projects/${projectId}/story`, label: "小说介绍" }} pathname={pathname} onNavigate={() => setMobileOpen(false)} icon={FileText} />
            <NavLink item={{ href: `/projects/${projectId}/chapters`, label: "章节目录" }} pathname={pathname} onNavigate={() => setMobileOpen(false)} icon={BookOpen} />
            {chapters.slice(0, 6).map((chapter) => <Link key={chapter.id} href={`/projects/${projectId}/chapters/${chapter.chapter_number}`} onClick={() => setMobileOpen(false)} className={cn("block truncate rounded-lg px-3 py-2 pl-11 text-xs text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900", pathname === `/projects/${projectId}/chapters/${chapter.chapter_number}` && "bg-slate-100 text-slate-950")}>第 {chapter.chapter_number} 章 · {chapter.title || "未命名章节"}</Link>)}
          </div>
        ) : null}
        {groups.map((group) => {
          const isLibrary = group.title === "资料库";
          return <div key={group.title} className="mt-4 space-y-1"><div className="flex items-center justify-between px-3 pb-1"><p className="text-[11px] font-semibold tracking-[0.12em] text-slate-400">{group.title}</p>{isLibrary ? <button type="button" aria-label={libraryOpen ? "收起资料库" : "展开资料库"} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={() => setLibraryOpen((open) => !open)}><ChevronDown aria-hidden="true" className={cn("size-4 transition-transform", libraryOpen && "rotate-180")} /></button> : null}</div>{(!isLibrary || libraryOpen) && group.items.map((item) => <NavLink key={item.href} item={item} pathname={pathname} onNavigate={() => setMobileOpen(false)} />)}</div>;
        })}
      </nav>
      <div className="border-t border-slate-100 p-4"><NavLink item={{ href: "/settings", label: "AI 设置" }} pathname={pathname} onNavigate={() => setMobileOpen(false)} icon={Settings2} /></div>
    </aside>
  );

  if (isChapterEditor) {
    return <div className="min-h-dvh bg-[var(--workspace-bg)] text-foreground"><main className="min-h-dvh min-w-0 p-0">{children}</main></div>;
  }

  return <div className="min-h-dvh bg-[var(--workspace-bg)] text-foreground"><button type="button" aria-label="打开导航" className="fixed left-4 top-4 z-50 flex size-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm md:hidden" onClick={() => setMobileOpen(true)}><Menu aria-hidden="true" className="size-5" /></button><div className={cn("fixed inset-0 z-40 bg-slate-950/20 transition-opacity md:hidden", mobileOpen ? "opacity-100" : "pointer-events-none opacity-0")} onClick={() => setMobileOpen(false)} aria-hidden="true" /><div className={cn("fixed inset-y-0 left-0 z-50 transition-transform duration-200 md:hidden", mobileOpen ? "translate-x-0" : "-translate-x-full")}><div className="relative h-full">{sidebar}<button type="button" aria-label="关闭导航" className="absolute right-3 top-5 flex size-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100" onClick={() => setMobileOpen(false)}><X aria-hidden="true" className="size-5" /></button></div></div><div className="fixed inset-y-0 left-0 z-30 hidden md:block">{sidebar}</div><main className="min-h-dvh min-w-0 px-4 py-16 sm:px-6 md:ml-[220px] md:px-8 md:py-10 xl:px-12">{children}</main></div>;
}

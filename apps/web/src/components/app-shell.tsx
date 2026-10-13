"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  extractProjectId,
  getGlobalNav,
  getProjectNavGroups,
  isNavActive,
  type NavItem,
} from "@/lib/nav";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Chapter, Project } from "@/lib/types";

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = isNavActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      className={cn(
        buttonVariants({ variant: active ? "secondary" : "ghost", size: "sm" }),
        "w-full justify-start",
      )}
    >
      {item.label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const projectId = extractProjectId(pathname);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const groups = projectId ? getProjectNavGroups(projectId) : [];

  useEffect(() => {
    if (!projectId) {
      setProject(null);
      setChapters([]);
      return;
    }
    Promise.all([
      api<Project>(`/projects/${projectId}`),
      api<Chapter[]>(`/projects/${projectId}/chapters`),
    ])
      .then(([loadedProject, loadedChapters]) => {
        setProject(loadedProject);
        setChapters(loadedChapters);
      })
      .catch(() => {
        setProject(null);
        setChapters([]);
      });
  }, [projectId, pathname]);

  return (
    <div className="min-h-screen overflow-hidden bg-background">
      <aside className="fixed inset-y-0 left-0 z-40 flex h-screen w-60 flex-col border-r bg-sidebar text-sidebar-foreground">
        <div className="border-b px-4 py-4">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            AI 小说工作室
          </Link>
          <p className="mt-1 text-xs text-muted-foreground">狼人罗曼史 MVP · 人机协作</p>
        </div>
        <nav className="flex flex-1 flex-col gap-4 overflow-y-auto p-3">
          <div className="flex flex-col gap-1">
            {getGlobalNav()
              .filter((item) => item.href !== "/settings")
              .map((item) => (
              <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            <Link
              href="/projects"
              className="rounded-md px-3 py-1 text-xs text-primary hover:bg-accent hover:underline"
            >
              + 创建新书
            </Link>
          </div>

          {projectId ? (
            <div className="flex flex-col gap-1 border-y py-3">
              <p className="truncate px-2 text-sm font-semibold" title={project?.title || "当前小说"}>
                {project?.title || "当前小说"}
              </p>
              <NavLink
                item={{ href: `/projects/${projectId}/story`, label: "小说介绍" }}
                pathname={pathname}
              />
              <NavLink
                item={{ href: `/projects/${projectId}/chapters`, label: "章节目录" }}
                pathname={pathname}
              />
              {chapters.map((chapter) => (
                <Link
                  key={chapter.id}
                  href={`/projects/${projectId}/chapters/${chapter.chapter_number}`}
                  className={cn(
                    "truncate rounded-md px-3 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    pathname === `/projects/${projectId}/chapters/${chapter.chapter_number}` && "bg-accent text-accent-foreground",
                  )}
                >
                  第 {chapter.chapter_number} 章 · {chapter.title === `Chapter ${chapter.chapter_number}` && chapter.chapter_number === 1 ? "The Rejection" : chapter.title || "未命名章节"}
                </Link>
              ))}
              <Link
                href={`/projects/${projectId}/chapters`}
                className="px-3 py-1 text-xs text-primary hover:underline"
              >
                + 新建章节
              </Link>
            </div>
          ) : null}

          {groups.map((group) => {
            const isLibrary = group.title === "资料库";
            return (
              <div key={group.title} className="flex flex-col gap-1">
                <div className="flex items-center justify-between px-2">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {group.title}
                  </p>
                  {isLibrary ? (
                    <button
                      type="button"
                      className="text-[11px] text-muted-foreground underline-offset-2 hover:underline"
                      onClick={() => setLibraryOpen((open) => !open)}
                    >
                      {libraryOpen ? "收起" : "展开"}
                    </button>
                  ) : null}
                </div>
                {(!isLibrary || libraryOpen) &&
                  group.items.map((item) => (
                    <NavLink key={item.href} item={item} pathname={pathname} />
                  ))}
              </div>
            );
          })}
          <div className="mt-auto mb-[100px] border-t pt-3">
            <NavLink item={{ href: "/settings", label: "AI 设置" }} pathname={pathname} />
          </div>
        </nav>
      </aside>
      <main className="ml-60 h-screen min-w-0 overflow-y-auto p-6">{children}</main>
    </div>
  );
}

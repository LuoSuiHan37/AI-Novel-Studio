"use client";

import Link from "next/link";
import { BookOpen, ChevronDown, FileText, FolderOpen, House, List, PencilLine, ShieldCheck, Sparkles, Users, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { displayProjectTitle, projectCoverUrl } from "@/lib/project-display";
import type { Project } from "@/lib/types";

type Props = { projectId: string; project: Project | null; pathname: string; mobile?: boolean; onClose?: () => void };

function NavItem({ href, label, pathname, icon: Icon, onClose }: { href: string; label: string; pathname: string; icon: typeof House; onClose?: () => void }) {
  const active = href.endsWith("/chapters") ? pathname.includes("/chapters") : href === `/projects/${pathname.split("/")[2]}` ? pathname.split("/").length === 3 : pathname === href || pathname.startsWith(`${href}/`);
  return <Link href={href} onClick={onClose} aria-current={active ? "page" : undefined} className={cn("flex min-h-11 items-center gap-3 rounded-[10px] px-3.5 text-[14px] font-medium transition-colors", active ? "bg-[#edf3ff] text-[#2563eb]" : "text-[#42516b] hover:bg-[#f4f7fb] hover:text-[#14213d]")}><Icon className="size-[18px]" strokeWidth={1.8} /><span>{label}</span></Link>;
}

export function ProjectSidebar({ projectId, project, pathname, mobile, onClose }: Props) {
  const base = `/projects/${projectId}`;
  const cover = projectCoverUrl(project);
  return <aside className={cn("flex h-full w-[220px] flex-col border-r border-[#e4eaf3] bg-white text-[#14213d]", mobile && "shadow-2xl")}>
    <div className="flex h-[72px] shrink-0 items-center justify-between border-b border-[#eef2f7] px-5">
      <Link href="/" onClick={onClose} className="flex items-center gap-2.5"><span className="flex size-8 items-center justify-center rounded-[9px] bg-[#2563eb] text-white shadow-[0_5px_12px_rgba(37,99,235,.2)]"><BookOpen className="size-[19px]" /></span><span className="text-[16px] font-semibold tracking-[-.02em]">AI 小说工作室</span></Link>
      {mobile ? <button type="button" aria-label="关闭导航" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="size-5" /></button> : null}
    </div>
    <div className="border-b border-[#eef2f7] px-4 py-4"><Link href="/" onClick={onClose} className="flex items-center gap-2 rounded-lg px-2 py-2 text-[14px] font-medium text-[#42516b] hover:bg-[#f4f7fb]"><span className="text-lg leading-none">‹</span>返回作品库</Link></div>
    <div className="border-b border-[#eef2f7] px-4 py-4"><div className="flex items-center gap-3"><div className="size-11 shrink-0 overflow-hidden rounded-[9px] bg-[linear-gradient(145deg,#e8effb,#9db5dd)]">{cover ? <img src={cover} alt="" className="size-full object-cover" /> : <div className="flex size-full items-center justify-center text-[#2563eb]"><BookOpen className="size-5" /></div>}</div><div className="min-w-0"><p className="truncate text-[14px] font-semibold">{displayProjectTitle(project)}</p><p className="mt-1 truncate text-xs text-[#8a96aa]">{project?.genre || "未设置题材"}</p></div></div></div>
    <nav aria-label="作品导航" className="flex-1 overflow-y-auto px-3 py-4"><div className="space-y-1">
      <NavItem href={base} label="概览" pathname={pathname} icon={House} onClose={onClose} />
      <NavItem href={`${base}/story`} label="小说介绍" pathname={pathname} icon={FileText} onClose={onClose} />
      <NavItem href={`${base}/characters`} label="策划" pathname={pathname} icon={PencilLine} onClose={onClose} />
      <NavItem href={`${base}/chapters`} label="章节目录" pathname={pathname} icon={List} onClose={onClose} />
      <NavItem href={`${base}/quality`} label="独立审核" pathname={pathname} icon={ShieldCheck} onClose={onClose} />
    </div><div className="mt-5 border-t border-[#eef2f7] pt-4"><div className="flex items-center justify-between px-3 pb-2 text-[11px] font-semibold tracking-[.12em] text-[#9aa6b8]"><span>资料库</span><ChevronDown className="size-3.5" /></div><div className="space-y-1"><NavItem href={`${base}/bible`} label="书级创作内核" pathname={pathname} icon={BookOpen} onClose={onClose} /><NavItem href={`${base}/characters`} label="角色" pathname={pathname} icon={Users} onClose={onClose} /><NavItem href={`${base}/world`} label="世界观" pathname={pathname} icon={FolderOpen} onClose={onClose} /><NavItem href={`${base}/hooks`} label="钩子 / 伏笔" pathname={pathname} icon={Sparkles} onClose={onClose} /></div></div></nav>
  </aside>;
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, BookOpen, Check, ChevronDown, Clock3, Grid2X2, List, MoreHorizontal, Plus, Search, Settings2, Trash2, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { genreLabel, platformLabel, projectStatusLabel } from "@/lib/labels";
import type { Chapter, Project, StoryBible } from "@/lib/types";

type Filter = "all" | "writing" | "planning" | "completed";
type PlatformFilter = "all" | "fanqie" | "qidian" | "qimao" | "zongheng" | "shuqi" | "other";
type ProjectSummary = { project: Project; chapters: Chapter[]; story: StoryBible | null };
const PLATFORM_FILTERS: Array<[PlatformFilter, string]> = [["all", "全部平台"], ["fanqie", "番茄"], ["qidian", "起点"], ["qimao", "七猫"], ["zongheng", "纵横"], ["shuqi", "书旗"], ["other", "其他平台"]];

function PlatformFilterSelect({ value, onChange }: { value: PlatformFilter; onChange: (value: PlatformFilter) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const current = PLATFORM_FILTERS.find(([key]) => key === value)?.[1] || "全部平台";
  useEffect(() => {
    function close(event: MouseEvent) { if (!root.current?.contains(event.target as Node)) setOpen(false); }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return <div ref={root} className="relative"><button type="button" aria-label="按发布平台筛选" aria-haspopup="listbox" aria-expanded={open} onKeyDown={(event) => { if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") { event.preventDefault(); setOpen(true); } if (event.key === "Escape") setOpen(false); }} onClick={() => setOpen((currentOpen) => !currentOpen)} className={`inline-flex h-9 min-w-[124px] items-center justify-between gap-3 rounded-lg border px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 ${open || value !== "all" ? "border-blue-200 bg-blue-50 text-primary" : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50/50"}`}><span>{current}</span><ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} /></button>{open ? <div role="listbox" aria-label="发布平台" className="absolute right-0 top-11 z-30 w-44 overflow-hidden rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_14px_32px_rgba(30,55,95,.14)]">{PLATFORM_FILTERS.map(([key, label]) => <button key={key} type="button" role="option" aria-selected={value === key} onClick={() => { onChange(key); setOpen(false); }} className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition ${value === key ? "bg-blue-50 font-semibold text-primary" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"}`}><span>{label}</span>{value === key ? <Check aria-hidden="true" className="size-4" /> : null}</button>)}</div> : null}</div>;
}

function displayTitle(project: Project): string {
  const title = project.title?.trim();
  if (!title || /^待生成书名-/.test(title) || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(title)) return "未命名作品";
  return title;
}

function formatDate(value?: string): string {
  if (!value) return "更新时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "更新时间未知";
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function classify(project: Project): Exclude<Filter, "all"> {
  if (project.status === "completed") return "completed";
  if (project.status === "writing" || project.status === "revising" || ["drafting", "review", "publish"].includes(project.current_stage)) return "writing";
  return "planning";
}

function coverUrl(project: Project): string | null {
  const value = project.extra_metadata?.cover_url;
  return typeof value === "string" && value.trim() ? value : null;
}

function Cover({ project, small = false }: { project: Project; small?: boolean }) {
  const url = coverUrl(project);
  return url ? <div role="img" aria-label={`${displayTitle(project)}封面`} className={`h-full w-full bg-cover bg-center ${small ? "rounded-xl" : "rounded-2xl"}`} style={{ backgroundImage: `url(${url})` }} /> : <div className={`flex h-full w-full flex-col justify-between overflow-hidden bg-[linear-gradient(145deg,#e8effb_0%,#cbd9f1_52%,#9db5dd_100%)] p-3 text-blue-950 ${small ? "rounded-xl" : "rounded-2xl"}`}><BookOpen aria-hidden="true" className="size-5 opacity-70" /><span className="font-serif text-lg leading-tight">{displayTitle(project)}</span></div>;
}

function summaryText(item: ProjectSummary): string {
  return item.story?.synopsis || item.story?.logline || item.project.logline || "还没有简介，进入作品后完善故事设定。";
}

function latestChapter(item: ProjectSummary): Chapter | null {
  return [...item.chapters].sort((a, b) => {
    const timeA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
    const timeB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
    return timeB - timeA || b.chapter_number - a.chapter_number;
  }).find((chapter) => Boolean(chapter.content?.trim())) || [...item.chapters].sort((a, b) => b.chapter_number - a.chapter_number)[0] || null;
}

function ContinueCard({ item }: { item: ProjectSummary }) {
  const { project, chapters } = item;
  const chapter = latestChapter(item);
  const target = project.chapter_count_target;
  const wordCount = chapters.reduce((total, current) => total + (current.word_count || 0), 0);
  const progress = target ? Math.min(100, Math.round((chapters.length / target) * 100)) : null;
  const href = chapter ? `/projects/${project.id}/chapters/${chapter.chapter_number}` : `/projects/${project.id}`;
  return (
    <section className="relative overflow-hidden rounded-2xl border border-blue-100 bg-white shadow-[var(--shadow-card)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(37,99,235,0.12),transparent_38%),linear-gradient(110deg,rgba(255,255,255,0.98),rgba(239,245,255,0.88))]" />
      <div className="relative p-5 sm:p-7">
        <div className="mb-5 flex items-center justify-between"><div className="flex items-center gap-3"><span className="h-6 w-1 rounded-full bg-primary" /><h2 className="text-lg font-semibold text-slate-900">继续创作</h2></div><Link href={`/projects/${project.id}/bible`} aria-label="打开书级创作内核" className="rounded-lg p-2 text-slate-500 hover:bg-white/80 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"><MoreHorizontal aria-hidden="true" className="size-5" /></Link></div>
        <div className="grid gap-6 lg:grid-cols-[170px_minmax(0,1fr)_230px] lg:items-center">
          <div className="h-52 w-36 shrink-0 sm:h-60 sm:w-40"><Cover project={project} /></div>
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2"><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">{genreLabel(project.genre)}</span>{project.tropes.slice(0, 2).map((trope) => <span key={trope} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{trope}</span>)}</div>
            <h3 className="mt-4 font-serif text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{displayTitle(project)}</h3>
            <p className="mt-4 max-w-2xl text-[15px] leading-7 text-slate-600">{summaryText(item)}</p>
            <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm font-medium text-slate-700"><span>{chapters.length} 章</span><span>{wordCount.toLocaleString("zh-CN")} 字</span>{chapter ? <span className="inline-flex items-center gap-1.5 text-slate-500"><Clock3 aria-hidden="true" className="size-4" />上次编辑：第 {chapter.chapter_number} 章</span> : null}</div>
            <p className="mt-2 text-sm text-slate-500">{formatDate(project.updated_at)}</p>
          </div>
          <div className="flex flex-col gap-4 lg:items-stretch"><div className="min-h-11">{progress !== null ? <><div className="mb-2 flex items-center justify-between text-xs text-slate-500"><span>完成度</span><span>{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-blue-100"><div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${progress}%` }} /></div></> : <p className="text-sm text-slate-500">尚未设置目标章节数</p>}</div><Link href={href} className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-white shadow-[0_8px_18px_rgba(37,99,235,0.22)] transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50">{chapter ? "继续创作" : "进入作品策划"}<ArrowRight aria-hidden="true" className="size-5" /></Link></div>
        </div>
      </div>
    </section>
  );
}

function ProjectCard({ item, list, onDelete, onEditPlatform }: { item: ProjectSummary; list?: boolean; onDelete: (project: Project) => void; onEditPlatform: (project: Project) => void }) {
  const { project, chapters } = item;
  const wordCount = chapters.reduce((total, current) => total + (current.word_count || 0), 0);
  return <article className={list ? "flex min-w-0 gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-card)]" : "flex min-w-0 gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-[var(--shadow-card)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[var(--shadow-float)]"}>
    <Link href={`/projects/${project.id}`} className={list ? "h-32 w-24 shrink-0" : "h-36 w-24 shrink-0"} aria-label={`打开${displayTitle(project)}`}><Cover project={project} small /></Link>
    <div className="flex min-w-0 flex-1 flex-col"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-serif text-xl font-semibold text-slate-950">{displayTitle(project)}</p><p className="mt-1 text-xs text-slate-500">{genreLabel(project.genre)} · {projectStatusLabel(project.status)}</p><span className="mt-2 inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">{platformLabel(project.target_platform) || "未设置平台"}</span></div><details className="relative"><summary className="flex size-9 cursor-pointer list-none items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-800 [&::-webkit-details-marker]:hidden" aria-label={`更多${displayTitle(project)}操作`}><MoreHorizontal aria-hidden="true" className="size-5" /></summary><div className="absolute right-0 top-10 z-20 w-40 rounded-xl border border-slate-200 bg-white p-1.5 text-sm shadow-[var(--shadow-float)]"><Link className="block rounded-lg px-3 py-2 hover:bg-slate-50" href={`/projects/${project.id}`}>进入作品</Link><Link className="block rounded-lg px-3 py-2 hover:bg-slate-50" href={`/projects/${project.id}/bible`}>书级创作内核</Link><Link className="block rounded-lg px-3 py-2 hover:bg-slate-50" href={`/projects/${project.id}/research`}>参考研究</Link><button type="button" onClick={() => onEditPlatform(project)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-slate-50"><Check aria-hidden="true" className="size-4" />设置平台</button><button type="button" onClick={() => onDelete(project)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-red-600 hover:bg-red-50"><Trash2 aria-hidden="true" className="size-4" />删除作品</button></div></details></div><p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-600">{summaryText(item)}</p><div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-4 text-sm text-slate-500"><span>{chapters.length} 章</span><span>{wordCount.toLocaleString("zh-CN")} 字</span><span>{formatDate(project.updated_at)}</span></div></div>
  </article>;
}

export default function DashboardPage() {
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Project | null>(null);
  const [platformEditing, setPlatformEditing] = useState<Project | null>(null);
  const [platformDraft, setPlatformDraft] = useState("fanqie");
  const [savingPlatform, setSavingPlatform] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(async () => {
      const projects = await api<Project[]>("/projects");
      const summaries = await Promise.all(projects.map(async (project) => {
        const [chapters, story] = await Promise.all([
          api<Chapter[]>(`/projects/${project.id}/chapters`).catch(() => []),
          api<StoryBible>(`/projects/${project.id}/story`).catch(() => null),
        ]);
        return { project, chapters, story };
      }));
      if (active) setItems(summaries);
    }).catch((err: unknown) => { if (active) setError(err instanceof ApiError ? err.message : "加载工作台失败"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return [...items].filter(({ project }) => filter === "all" || classify(project) === filter).filter(({ project }) => platformFilter === "all" || (platformFilter === "other" ? !["fanqie", "qidian", "qimao", "zongheng", "shuqi"].includes(project.target_platform || "") : project.target_platform === platformFilter)).filter(({ project, story }) => !needle || [displayTitle(project), project.genre, project.target_platform, story?.synopsis, story?.logline, project.logline].some((value) => value?.toLowerCase().includes(needle))).sort((a, b) => new Date(b.project.updated_at || b.project.created_at || 0).getTime() - new Date(a.project.updated_at || a.project.created_at || 0).getTime());
  }, [filter, items, platformFilter, query]);

  async function deleteProject() {
    if (!pendingDelete) return;
    setDeleting(true); setError(null);
    try { await api(`/projects/${pendingDelete.id}`, { method: "DELETE" }); setItems((current) => current.filter((item) => item.project.id !== pendingDelete.id)); setPendingDelete(null); }
    catch (err) { setError(err instanceof ApiError ? err.message : "删除作品失败，请稍后重试"); }
    finally { setDeleting(false); }
  }

  async function savePlatform() {
    if (!platformEditing) return;
    setSavingPlatform(true); setError(null);
    try { const updated = await api<Project>(`/projects/${platformEditing.id}`, { method: "PATCH", body: JSON.stringify({ target_platform: platformDraft }) }); setItems((current) => current.map((item) => item.project.id === updated.id ? { ...item, project: updated } : item)); setPlatformEditing(null); }
    catch (err) { setError(err instanceof ApiError ? err.message : "保存平台失败，请稍后重试"); }
    finally { setSavingPlatform(false); }
  }

  const continued = items.length ? [...items].sort((a, b) => new Date(b.project.updated_at || b.project.created_at || 0).getTime() - new Date(a.project.updated_at || a.project.created_at || 0).getTime()).find((item) => item.chapters.length > 0) : null;
  const filterOptions: Array<[Filter, string]> = [["all", "全部"], ["writing", "写作中"], ["planning", "策划中"], ["completed", "已完成"]];

  return <section className="mx-auto w-full max-w-[1440px] space-y-8">
    <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><p className="mb-2 text-xs font-semibold tracking-[0.18em] text-primary">AI + HUMAN CREATIVE SYSTEM</p><h1 className="font-serif text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">创作工作台</h1><p className="mt-3 text-base text-slate-500">让每一个故事，向前一步</p></div><div className="flex flex-col gap-3 sm:flex-row sm:items-center"><label className="relative block"><span className="sr-only">搜索作品、角色、设置或灵感</span><Search aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索作品、角色、设置、灵感…" className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-11 pr-4 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/15 sm:w-72" /></label><Link href="/settings" className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-blue-200 bg-white px-4 text-sm font-semibold text-primary shadow-sm transition hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"><Settings2 aria-hidden="true" className="size-4" />AI 设置</Link><Link href="/projects?create=1" className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-white shadow-[0_8px_18px_rgba(37,99,235,0.2)] transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"><Plus aria-hidden="true" className="size-5" />新建小说</Link></div></header>
    {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-500 shadow-[var(--shadow-card)]" role="status">正在加载你的作品…</div> : error ? <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-700" role="alert">{error}</div> : null}
    {!loading && !error && continued ? <ContinueCard item={continued} /> : null}
    {!loading && !error && !items.length ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-[var(--shadow-card)]"><div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-blue-50 text-primary"><BookOpen aria-hidden="true" className="size-7" /></div><h2 className="mt-4 font-serif text-2xl font-semibold text-slate-950">从一个故事开始</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">还没有作品。创建一本小说后，策划、参考研究和章节创作都会在这里汇总。</p><Link href="/projects?create=1" className="mt-5 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-white hover:bg-blue-700"><Plus aria-hidden="true" className="size-5" />新建小说</Link></div> : null}
    {!loading && !error && items.length ? <section aria-labelledby="library-heading"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex flex-wrap items-center gap-2"><h2 id="library-heading" className="mr-2 font-serif text-3xl font-semibold text-slate-950">我的作品</h2>{filterOptions.map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)} className={`min-h-10 rounded-full px-4 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${filter === value ? "bg-blue-50 text-primary" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"}`}>{label}</button>)}</div><div className="flex flex-wrap items-center gap-2"><span className="text-sm text-slate-500">平台</span><PlatformFilterSelect value={platformFilter} onChange={setPlatformFilter} /><label className="flex items-center gap-1 text-sm text-slate-500">最近编辑<ChevronDown aria-hidden="true" className="size-4" /></label><div className="flex rounded-xl border border-slate-200 bg-white p-1"><button type="button" aria-label="网格视图" aria-pressed={view === "grid"} onClick={() => setView("grid")} className={`flex size-9 items-center justify-center rounded-lg ${view === "grid" ? "bg-blue-50 text-primary" : "text-slate-400 hover:text-slate-700"}`}><Grid2X2 aria-hidden="true" className="size-4" /></button><button type="button" aria-label="列表视图" aria-pressed={view === "list"} onClick={() => setView("list")} className={`flex size-9 items-center justify-center rounded-lg ${view === "list" ? "bg-blue-50 text-primary" : "text-slate-400 hover:text-slate-700"}`}><List aria-hidden="true" className="size-4" /></button></div></div></div>{filtered.length ? <div className={view === "grid" ? "mt-5 grid gap-4 xl:grid-cols-3" : "mt-5 grid gap-4"}>{filtered.map((item) => <ProjectCard key={item.project.id} item={item} list={view === "list"} onDelete={setPendingDelete} onEditPlatform={(project) => { setPlatformEditing(project); setPlatformDraft(project.target_platform || "fanqie"); }} />)}</div> : <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">没有匹配的作品。试试其他关键词或筛选条件。</div>}</section> : null}
    {platformEditing ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/25 p-4"><div role="dialog" aria-modal="true" aria-labelledby="platform-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><h2 id="platform-title" className="text-lg font-semibold text-slate-950">设置发布平台</h2><p className="mt-2 text-sm text-slate-600">为“{displayTitle(platformEditing)}”选择主要发布平台。</p></div><button type="button" aria-label="取消设置平台" onClick={() => setPlatformEditing(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X aria-hidden="true" className="size-5" /></button></div><label className="mt-5 block text-sm font-medium text-slate-700">发布平台<select value={platformDraft} onChange={(event) => setPlatformDraft(event.target.value)} className="mt-2 h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"><option value="fanqie">番茄</option><option value="qidian">起点</option><option value="qimao">七猫</option><option value="zongheng">纵横</option><option value="shuqi">书旗</option><option value="alphanovel">AlphaNovel</option><option value="wattpad">Wattpad</option><option value="goodnovel">GoodNovel</option></select></label><div className="mt-6 flex justify-end gap-2"><Button variant="outline" onClick={() => setPlatformEditing(null)} disabled={savingPlatform}>取消</Button><Button onClick={() => void savePlatform()} disabled={savingPlatform}>{savingPlatform ? "保存中…" : "保存平台"}</Button></div></div></div> : null}
    {pendingDelete ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/25 p-4" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><h2 id="delete-title" className="text-lg font-semibold text-slate-950">删除这部作品？</h2><p className="mt-2 text-sm leading-6 text-slate-600">“{displayTitle(pendingDelete)}”及其章节、角色和创作资料都会被永久删除，无法恢复。</p></div><button type="button" aria-label="取消删除" onClick={() => setPendingDelete(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X aria-hidden="true" className="size-5" /></button></div><div className="mt-6 flex justify-end gap-2"><Button variant="outline" onClick={() => setPendingDelete(null)} disabled={deleting}>取消</Button><Button className="bg-red-600 hover:bg-red-700" onClick={() => void deleteProject()} disabled={deleting}>{deleting ? "删除中…" : "确认删除"}</Button></div></div></div> : null}
  </section>;
}

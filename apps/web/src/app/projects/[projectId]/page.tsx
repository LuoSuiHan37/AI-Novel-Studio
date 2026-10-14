"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { pipelineStageLabel, projectStatusLabel } from "@/lib/labels";
import { buildChecklist } from "@/lib/readiness";
import type {
  Chapter,
  Character,
  Foreshadowing,
  Hook,
  MasterPlot,
  NovelAudit,
  Project,
  StoryArc,
  StoryBible,
  WorldBible,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export default function NovelDashboardPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [story, setStory] = useState<StoryBible | null>(null);
  const [world, setWorld] = useState<WorldBible | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [plot, setPlot] = useState<MasterPlot | null>(null);
  const [arcs, setArcs] = useState<StoryArc[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [foreshadowing, setForeshadowing] = useState<Foreshadowing[]>([]);
  const [audit, setAudit] = useState<NovelAudit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showChecklist, setShowChecklist] = useState(false);

  const load = useCallback(async () => {
    const [item, storyRes, worldRes, characterRes, plotRes, arcRes, chapterRes, auditRes, hookRes, foreshadowingRes] = await Promise.all([
      api<Project>(`/projects/${projectId}`),
      api<StoryBible>(`/projects/${projectId}/story`).catch(() => null),
      api<WorldBible>(`/projects/${projectId}/world`).catch(() => null),
      api<Character[]>(`/projects/${projectId}/characters`).catch(() => []),
      api<MasterPlot>(`/projects/${projectId}/plot`).catch(() => null),
      api<StoryArc[]>(`/projects/${projectId}/arcs`).catch(() => []),
      api<Chapter[]>(`/projects/${projectId}/chapters`).catch(() => []),
      api<NovelAudit>(`/projects/${projectId}/audit`).catch(() => null),
      api<Hook[]>(`/projects/${projectId}/hooks`).catch(() => []),
      api<Foreshadowing[]>(`/projects/${projectId}/foreshadowing`).catch(() => []),
    ]);
    setProject(item);
    setStory(storyRes);
    setWorld(worldRes);
    setCharacters(characterRes);
    setPlot(plotRes);
    setArcs(arcRes);
    setChapters(chapterRes);
    setAudit(auditRes);
    setHooks(hookRes);
    setForeshadowing(foreshadowingRes);
  }, [projectId]);

  useEffect(() => {
    load()
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [load]);

  const checklist = useMemo(
    () =>
      buildChecklist(projectId, {
        story,
        world,
        characters,
        plot,
        arcs,
        chapters,
      }),
    [projectId, story, world, characters, plot, arcs, chapters],
  );

  const doneCount = checklist.filter((item) => item.done).length;
  const latest = [...chapters].sort((a, b) => b.chapter_number - a.chapter_number)[0];
  const chapterNo = latest?.chapter_number || 1;
  const targetChapters = audit?.planned_chapter_count ?? project?.chapter_count_target ?? null;
  const writtenChapters = chapters.filter((chapter) => chapter.content?.trim()).length;
  const approvedChapters = chapters.filter((chapter) => ["approved", "published"].includes(chapter.status)).length;
  const progressPercent = targetChapters ? Math.min(100, Math.round((writtenChapters / targetChapters) * 100)) : 0;
  const currentArc = arcs
    .filter((arc) => (arc.start_chapter_number ?? 1) <= chapterNo && (arc.end_chapter_number ?? Number.MAX_SAFE_INTEGER) >= chapterNo)
    .sort((left, right) => left.sequence - right.sequence)[0] ?? null;
  const nextBeat = plot?.beats
    .filter((beat) => beat.chapter_hint === null || beat.chapter_hint >= chapterNo)
    .sort((left, right) => (left.chapter_hint ?? Number.MAX_SAFE_INTEGER) - (right.chapter_hint ?? Number.MAX_SAFE_INTEGER))[0] ?? null;
  const openHooks = hooks.filter((item) => !["resolved", "paid_off", "closed"].includes(item.status));
  const openForeshadowing = foreshadowing.filter((item) => !["resolved", "paid_off", "closed"].includes(item.status));

  return (
    <section className="mx-auto max-w-5xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{project?.title || "小说概览"}</h1>
        {project ? (
          <p className="text-sm text-muted-foreground">
            {pipelineStageLabel(project.current_stage)} · {projectStatusLabel(project.status)} · 第 {chapterNo} 章
          </p>
        ) : null}
      </header>

      <StatusBanner loading={loading} error={error} />

      {project ? (
        <div className="rounded-xl border px-4 py-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-medium">全书进度与发布审计</p>
              <p className="mt-1 text-xs text-muted-foreground">
                已建立 {audit?.actual_chapter_count ?? chapters.length} 章 · 已写正文 {writtenChapters} 章 · 已确认 {approvedChapters} 章
              </p>
            </div>
            <span className={audit?.publishable ? "text-emerald-700" : "text-amber-700"}>
              {audit?.publishable ? "可发布" : "暂不可发布"}
            </span>
          </div>
          {targetChapters ? (
            <div className="mt-4" aria-label={`正文完成度 ${progressPercent}%`}>
              <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                <span>正文完成度</span>
                <span>{writtenChapters} / {targetChapters} 章 · {progressPercent}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          ) : null}
          {audit && !audit.publishable ? (
            <p className="mt-2 text-xs text-muted-foreground">
              缺失 {audit.missing_chapters.length} 章 · 未完成 {audit.unfinished_chapters.length} 章 · 重复 {audit.repetition_findings.length} 项 · 相关性问题 {audit.relevance_findings.length} 项
            </p>
          ) : null}
        </div>
      ) : null}

      {project ? (
        <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-xl border p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">主线位置</p>
                <h2 className="mt-1 text-lg font-semibold">{currentArc?.title || "尚未确定故事弧"}</h2>
              </div>
              <Link href={`/projects/${projectId}/arcs`} className="text-xs underline underline-offset-2">查看故事弧</Link>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {currentArc?.summary || "完善故事弧后，系统会在连续生成时使用对应阶段的目标和范围。"}
            </p>
            {currentArc ? (
              <p className="mt-3 text-xs text-muted-foreground">
                第 {currentArc.start_chapter_number ?? 1}–{currentArc.end_chapter_number ?? targetChapters ?? "—"} 章 · 当前在第 {chapterNo} 章
              </p>
            ) : null}
            <div className="mt-4 rounded-lg bg-muted/40 p-3">
              <p className="text-xs font-medium text-muted-foreground">下一条主线节点</p>
              <p className="mt-1 text-sm font-medium">{nextBeat?.name || "暂无明确节点"}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {nextBeat?.description || "建议在总大纲中补充带章节范围的关键事件。"}
              </p>
              {nextBeat?.chapter_hint ? <p className="mt-2 text-xs text-muted-foreground">计划在第 {nextBeat.chapter_hint} 章附近推进</p> : null}
            </div>
          </section>

          <section className="rounded-xl border p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">持续性记忆</p>
                <h2 className="mt-1 text-lg font-semibold">需要留意的线索</h2>
              </div>
              <Link href={`/projects/${projectId}/hooks`} className="text-xs underline underline-offset-2">查看全部</Link>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-2xl font-semibold tabular-nums">{openHooks.length}</p>
                <p className="mt-1 text-xs text-muted-foreground">未解决钩子</p>
              </div>
              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-2xl font-semibold tabular-nums">{openForeshadowing.length}</p>
                <p className="mt-1 text-xs text-muted-foreground">未回收伏笔</p>
              </div>
            </div>
            <div className="mt-3 space-y-2 text-xs text-muted-foreground">
              {[...openHooks.slice(0, 2).map((item) => `钩子：${item.description}`), ...openForeshadowing.slice(0, 2).map((item) => `伏笔：${item.description}`)].map((item) => (
                <p key={item} className="line-clamp-2">{item}</p>
              ))}
              {!openHooks.length && !openForeshadowing.length ? <p>目前没有待处理线索。</p> : null}
            </div>
          </section>
        </div>
      ) : null}

      <div className="rounded-xl border bg-muted/20 px-5 py-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">现在只需一步</p>
        <h2 className="mt-1 text-lg font-semibold">去写第 {chapterNo} 章</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          章节计划按需登记本书人物；不必提前创建所有配角。进编辑器后先生成计划。
        </p>
        <div className="mt-4">
          <Link href={`/projects/${projectId}/write`} className={cn(buttonVariants(), "inline-flex")}>
            去写第 {chapterNo} 章
          </Link>
        </div>
      </div>

      <button
        type="button"
        className="flex w-full items-center justify-between rounded-lg border px-4 py-3 text-left text-sm"
        onClick={() => setShowChecklist((value) => !value)}
      >
        <span className="font-medium">
          设定进度 {doneCount}/{checklist.length}
        </span>
        <span className="text-xs text-muted-foreground">{showChecklist ? "收起" : "展开（可改设定）"}</span>
      </button>
      {showChecklist ? (
        <ul className="divide-y rounded-xl border">
          {checklist.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <div className="min-w-0">
                <div className="font-medium">
                  <span className={item.done ? "text-foreground" : "text-muted-foreground"}>
                    {item.done ? "✓" : "○"} {item.label}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{item.hint}</p>
              </div>
              <Link href={item.href} className="shrink-0 text-xs underline underline-offset-2">
                {item.done ? "查看" : "去完成"}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

    </section>
  );
}

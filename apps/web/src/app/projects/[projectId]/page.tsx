"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { pipelineStageLabel, projectStatusLabel } from "@/lib/labels";
import { buildChecklist } from "@/lib/readiness";
import type { Chapter, Character, MasterPlot, NovelAudit, Project, StoryArc, StoryBible, WorldBible } from "@/lib/types";
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
  const [audit, setAudit] = useState<NovelAudit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showChecklist, setShowChecklist] = useState(false);

  const load = useCallback(async () => {
    const [item, storyRes, worldRes, characterRes, plotRes, arcRes, chapterRes, auditRes] = await Promise.all([
      api<Project>(`/projects/${projectId}`),
      api<StoryBible>(`/projects/${projectId}/story`).catch(() => null),
      api<WorldBible>(`/projects/${projectId}/world`).catch(() => null),
      api<Character[]>(`/projects/${projectId}/characters`).catch(() => []),
      api<MasterPlot>(`/projects/${projectId}/plot`).catch(() => null),
      api<StoryArc[]>(`/projects/${projectId}/arcs`).catch(() => []),
      api<Chapter[]>(`/projects/${projectId}/chapters`).catch(() => []),
      api<NovelAudit>(`/projects/${projectId}/audit`).catch(() => null),
    ]);
    setProject(item);
    setStory(storyRes);
    setWorld(worldRes);
    setCharacters(characterRes);
    setPlot(plotRes);
    setArcs(arcRes);
    setChapters(chapterRes);
    setAudit(auditRes);
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

  return (
    <section className="mx-auto max-w-3xl space-y-6">
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
                已有 {audit?.actual_chapter_count ?? chapters.length} / {audit?.planned_chapter_count ?? project.chapter_count_target ?? "未设定"} 章
              </p>
            </div>
            <span className={audit?.publishable ? "text-emerald-700" : "text-amber-700"}>
              {audit?.publishable ? "可发布" : "暂不可发布"}
            </span>
          </div>
          {audit && !audit.publishable ? (
            <p className="mt-2 text-xs text-muted-foreground">
              缺失 {audit.missing_chapters.length} 章 · 未完成 {audit.unfinished_chapters.length} 章 · 重复 {audit.repetition_findings.length} 项 · 相关性问题 {audit.relevance_findings.length} 项
            </p>
          ) : null}
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

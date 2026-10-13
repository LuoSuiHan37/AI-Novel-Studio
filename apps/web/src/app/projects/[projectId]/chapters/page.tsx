"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { chapterStatusLabel } from "@/lib/labels";
import type { Chapter, ChapterPlanSuggestion, Project } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ChaptersDirectoryPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [suggestingTitle, setSuggestingTitle] = useState(false);
  const [planSuggestion, setPlanSuggestion] = useState<ChapterPlanSuggestion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chapterTitle, setChapterTitle] = useState("");
  const nextNumber = useMemo(
    () => (chapters.length ? Math.max(...chapters.map((item) => item.chapter_number)) + 1 : 1),
    [chapters],
  );
  const orderedChapters = useMemo(
    () => [...chapters].sort((a, b) => a.chapter_number - b.chapter_number),
    [chapters],
  );

  async function load() {
    setLoading(true);
    try {
      const [loadedProject, loadedChapters] = await Promise.all([
        api<Project>(`/projects/${projectId}`),
        api<Chapter[]>(`/projects/${projectId}/chapters`),
      ]);
      setProject(loadedProject);
      setChapters(loadedChapters);
      // Keep the input empty so a numbering placeholder cannot be saved as
      // the actual chapter title.
      setChapterTitle("");
      setPlanSuggestion(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "章节目录加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => void load(), [projectId]);

  async function createNextChapter() {
    setBusy(true);
    setError(null);
    try {
      if (!planSuggestion) {
        throw new ApiError(400, "plan_required", "请先生成 AI 章节计划");
      }
      await api(`/projects/${projectId}/chapters/plan`, {
        method: "POST",
        projectId,
        body: JSON.stringify({
          ...planSuggestion,
          chapter_number: nextNumber,
          chapter_title: chapterTitle.trim(),
        }),
      });
      router.push(`/projects/${projectId}/chapters/${nextNumber}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "下一章创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function suggestPlan() {
    setSuggestingTitle(true);
    setError(null);
    try {
      const result = await api<ChapterPlanSuggestion>(
        `/projects/${projectId}/chapters/plan-suggestion`,
        {
          method: "POST",
          projectId,
          body: JSON.stringify({ chapter_number: nextNumber }),
        },
      );
      setPlanSuggestion(result);
      setChapterTitle(result.chapter_title);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "AI 章节计划生成失败");
    } finally {
      setSuggestingTitle(false);
    }
  }

  return (
    <section className="max-w-4xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{project?.title || "当前小说"}</h1>
          <p className="text-sm text-muted-foreground">每一章单独保存；确认后的章节会进入后续写作上下文。</p>
        </div>
      </div>
      <StatusBanner loading={loading} error={error} />
      <div className="flex max-w-2xl flex-wrap items-end gap-2 rounded-lg border bg-muted/20 p-3">
        <div className="flex-1">
          <label className="block space-y-1">
            <span className="text-xs font-medium text-muted-foreground">新章节名称</span>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              value={chapterTitle}
              onChange={(event) => setChapterTitle(event.target.value)}
              placeholder={`输入第 ${nextNumber} 章的名称，或先生成 AI 计划`}
            />
          </label>
        </div>
        <Button variant="outline" disabled={busy || suggestingTitle} onClick={() => void suggestPlan()}>
          {suggestingTitle ? "生成计划中…" : planSuggestion ? "重新生成章节计划" : "AI 生成章节计划"}
        </Button>
        <Button disabled={busy || suggestingTitle || !chapterTitle.trim() || !planSuggestion} onClick={() => void createNextChapter()}>
          {busy ? "创建中…" : `新建第 ${nextNumber} 章`}
        </Button>
      </div>
      {planSuggestion ? (
        <div className="max-w-2xl space-y-2 rounded-lg border p-3 text-sm">
          <h2 className="font-medium">AI 章节计划预览</h2>
          <p><span className="font-medium">目标：</span>{planSuggestion.chapter_goal}</p>
          <p><span className="font-medium">冲突：</span>{planSuggestion.conflict}</p>
          <p><span className="font-medium">情绪变化：</span>{planSuggestion.emotional_arc}</p>
          <p><span className="font-medium">章末钩子：</span>{planSuggestion.cliffhanger}</p>
          <ol className="list-inside list-decimal space-y-1 text-xs text-muted-foreground">
            {planSuggestion.scenes.map((scene) => (
              <li key={scene.scene_number}>{scene.goal}；冲突：{scene.conflict}；转折：{scene.turning_point}</li>
            ))}
          </ol>
        </div>
      ) : null}
      <div className="overflow-hidden rounded-lg border">
        {orderedChapters.map((chapter) => (
            <Link
              key={chapter.id}
              href={`/projects/${projectId}/chapters/${chapter.chapter_number}`}
              className="flex items-center justify-between border-b px-4 py-3 last:border-b-0 hover:bg-muted/40"
            >
              <div>
                <div className="font-medium">
                  第 {chapter.chapter_number} 章 · {chapter.title === `Chapter ${chapter.chapter_number}` && chapter.chapter_number === 1 ? "The Rejection" : chapter.title || "未命名章节"}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{chapter.word_count} 词</div>
              </div>
              <span className="text-xs text-muted-foreground">{chapterStatusLabel(chapter.status)}</span>
            </Link>
          ))}
        {!loading && chapters.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">还没有章节，从第 1 章开始。</div>
        ) : null}
      </div>
      <Link href={`/projects/${projectId}/story`} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex")}>
        先完善小说简介与总设定
      </Link>
    </section>
  );
}

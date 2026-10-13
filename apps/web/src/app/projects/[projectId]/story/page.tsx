"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { DEFAULT_STORY } from "@/lib/defaults";
import { confirmResource, tryAdvancePipeline } from "@/lib/hitl";
import { approvalStatusLabel } from "@/lib/labels";
import type { Project, StoryBible } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function StoryPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [form, setForm] = useState(DEFAULT_STORY);
  const [status, setStatus] = useState<string>("draft");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [projectTitle, setProjectTitle] = useState("");
  const [suggestedTitle, setSuggestedTitle] = useState("");
  const [suggestingTitle, setSuggestingTitle] = useState(false);
  const [applyingTitle, setApplyingTitle] = useState(false);

  useEffect(() => {
    Promise.all([api<StoryBible>(`/projects/${projectId}/story`), api<Project>(`/projects/${projectId}`)])
      .then(([bible, project]) => {
        setProjectTitle(project.title);
        const submission = bible.extra_metadata?.fanqie_submission || {};
        setForm({
          ...DEFAULT_STORY,
          ...bible,
          tropes: bible.tropes,
          logline: bible.logline || "",
          synopsis: bible.synopsis || "",
          target_reader: submission.target_reader || DEFAULT_STORY.target_reader,
          reading_tags: submission.reading_tags || [],
          content_tags: submission.content_tags || [],
          protagonist_names: submission.protagonist_names || [],
        });
        setStatus(bible.status);
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [projectId]);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function suggestNewTitle() {
    setSuggestingTitle(true);
    setError(null);
    setOk(null);
    try {
      const result = await api<{ title: string; available: boolean }>(
        `/projects/${projectId}/title-suggestion`,
        { method: "POST", projectId },
      );
      setSuggestedTitle(result.title);
      setOk(result.available ? "已生成新的可用书名，请确认是否采用。" : "已生成新书名，但仍可能与平台已有书名重复，请再次生成。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "AI 重新定义书名失败");
    } finally {
      setSuggestingTitle(false);
    }
  }

  async function applyNewTitle() {
    if (!suggestedTitle.trim()) return;
    setApplyingTitle(true);
    setError(null);
    try {
      const project = await api<Project>(`/projects/${projectId}`, {
        method: "PATCH",
        projectId,
        body: JSON.stringify({ title: suggestedTitle.trim() }),
      });
      setProjectTitle(project.title);
      setSuggestedTitle("");
      setOk("新书名已保存。提交番茄前仍建议在平台侧再次确认重名。 ");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存新书名失败");
    } finally {
      setApplyingTitle(false);
    }
  }

  async function saveAndConfirm() {
    const synopsisLength = String(form.synopsis || "").trim().length;
    const protagonistNames = Array.isArray(form.protagonist_names)
      ? form.protagonist_names.filter(Boolean)
      : [];
    if (synopsisLength < 50 || synopsisLength > 500) {
      setError(`番茄作品简介需要 50–500 字，当前为 ${synopsisLength} 字。`);
      return;
    }
    if (protagonistNames.length > 2 || protagonistNames.some((name) => name.length > 5)) {
      setError("最多填写两位主角，每个名字不超过 5 个字。 ");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<StoryBible>(`/projects/${projectId}/story`, {
        method: "PATCH",
        body: JSON.stringify({
          premise: form.premise,
          theme: form.theme,
          tone: form.tone,
          narrative_style: form.narrative_style,
          pov: form.pov,
          tense: form.tense,
          target_word_count: form.target_word_count,
          chapter_word_count: form.chapter_word_count,
          romance_level: form.romance_level,
          violence_level: form.violence_level,
          heat_level: form.heat_level,
          tropes: String(form.tropes)
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          logline: form.logline || null,
          synopsis: form.synopsis || null,
          target_reader: form.target_reader,
          reading_tags: form.reading_tags,
          content_tags: form.content_tags,
          protagonist_names: protagonistNames,
        }),
        projectId,
      });
      setStatus(saved.status);
      if (saved.status !== "approved") {
        await confirmResource(
          `/projects/${projectId}/story/submit`,
          `/projects/${projectId}/story/approve`,
          projectId,
        );
        const bible = await api<StoryBible>(`/projects/${projectId}/story`);
        setStatus(bible.status);
      }
      await tryAdvancePipeline(projectId);
      setOk("故事圣经已保存，已自动确定。可回概览看下一步。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  const synopsisLength = String(form.synopsis || "").trim().length;
  const protagonistNames = Array.isArray(form.protagonist_names) ? form.protagonist_names : ["", ""];
  const tagText = (value: unknown) => Array.isArray(value) ? value.join(", ") : "";

  return (
    <section className="max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">故事圣经</h1>
          <p className="text-sm font-medium">当前书名：{projectTitle || "加载中…"}</p>
          <p className="text-sm text-muted-foreground">
            状态：{approvalStatusLabel(status)} · 保存后自动进入后续流程
          </p>
        </div>
        <Link href={`/projects/${projectId}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
          回概览
        </Link>
      </div>
      <StatusBanner loading={loading} error={error} ok={ok} />
      <div className="rounded-lg border border-dashed border-border bg-muted/20 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">书名重复？让 AI 重新定义</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              AI 会读取当前作品简介、主题、标签和已生成章节，再提出贴合作品的新书名；不会重新生成故事。
            </p>
          </div>
          <Button variant="outline" disabled={suggestingTitle || loading} onClick={() => void suggestNewTitle()}>
            {suggestingTitle ? "结合章节分析中…" : "AI 重新定义书名"}
          </Button>
        </div>
        {suggestedTitle ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md bg-background p-3">
            <span className="text-sm">建议书名：</span>
            <span className="font-semibold">{suggestedTitle}</span>
            <Button size="sm" disabled={applyingTitle} onClick={() => void applyNewTitle()}>
              {applyingTitle ? "保存中…" : "采用此书名"}
            </Button>
            <Button size="sm" variant="ghost" disabled={suggestingTitle} onClick={() => void suggestNewTitle()}>
              再生成一个
            </Button>
          </div>
        ) : null}
      </div>
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <h2 className="font-semibold">番茄新书介绍</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          以下字段对应番茄创建新书页面；内部创作字段仍保留在下方，不会混用。
        </p>
      </div>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">目标读者</span>
        <select
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={form.target_reader}
          onChange={(event) => set("target_reader", event.target.value)}
        >
          <option value="male">男频</option>
          <option value="female">女频</option>
        </select>
      </label>
      <Field
        label="阅读标签（逗号分隔）"
        value={tagText(form.reading_tags)}
        onChange={(value) => set("reading_tags", value.split(",").map((item) => item.trim()).filter(Boolean))}
      />
      <Field
        label="内容标签（逗号分隔）"
        value={tagText(form.content_tags)}
        onChange={(value) => set("content_tags", value.split(",").map((item) => item.trim()).filter(Boolean))}
      />
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="主角名 1（最多 5 字）" value={protagonistNames[0] || ""} onChange={(value) => set("protagonist_names", [value, protagonistNames[1] || ""].filter(Boolean))} />
        <Field label="主角名 2（最多 5 字）" value={protagonistNames[1] || ""} onChange={(value) => set("protagonist_names", [protagonistNames[0] || "", value].filter(Boolean))} />
      </div>
      <div>
        <Field label="作品简介（50–500 字；不能出现低俗、暴力、血腥等违规内容）" value={form.synopsis || ""} onChange={(v) => set("synopsis", v)} multiline rows={7} />
        <p className={`mt-1 text-right text-xs ${synopsisLength < 50 || synopsisLength > 500 ? "text-destructive" : "text-muted-foreground"}`}>
          {synopsisLength}/500
        </p>
      </div>
      <div className="border-t pt-5">
        <h2 className="font-semibold">内部故事圣经</h2>
        <p className="mt-1 text-sm text-muted-foreground">这些字段服务 AI 长篇创作，不直接提交为番茄作品简介。</p>
      </div>
      <Field label="Premise（前提）" value={form.premise} onChange={(v) => set("premise", v)} multiline rows={4} />
      <Field label="Theme（主题）" value={form.theme} onChange={(v) => set("theme", v)} />
      <Field label="Tone（基调）" value={form.tone} onChange={(v) => set("tone", v)} />
      <Field label="Logline（一句话）" value={form.logline || ""} onChange={(v) => set("logline", v)} />
      <Field
        label="Tropes（逗号分隔）"
        value={Array.isArray(form.tropes) ? form.tropes.join(", ") : ""}
        onChange={(v) => set("tropes", v.split(",").map((item) => item.trim()).filter(Boolean))}
      />
      <Button disabled={busy} onClick={() => void saveAndConfirm()}>
        {busy ? "保存中…" : "保存"}
      </Button>
    </section>
  );
}

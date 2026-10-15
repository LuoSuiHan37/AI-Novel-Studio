"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { confirmResource, tryAdvancePipeline } from "@/lib/hitl";
import { approvalStatusLabel } from "@/lib/labels";
import type { StoryArc } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ArcsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [items, setItems] = useState<StoryArc[]>([]);
  const [title, setTitle] = useState("Rejection Arc");
  const [summary, setSummary] = useState("Public rejection and exile.");
  const [sequence, setSequence] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const arcs = await api<StoryArc[]>(`/projects/${projectId}/arcs`);
    setItems(arcs);
    // Research injection may already seed arcs 1..N. New arcs should start
    // after the existing sequence instead of submitting the form's old
    // default of 1 and triggering the uniqueness guard.
    const nextSequence = arcs.reduce((max, item) => Math.max(max, item.sequence), 0) + 1;
    setSequence(String(nextSequence));
  }, [projectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load()
        .catch((err: ApiError) => setError(err.message))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function createAndConfirm() {
    setBusy(true);
    setError(null);
    try {
      const created = await api<StoryArc>(`/projects/${projectId}/arcs`, {
        method: "POST",
        projectId,
        body: JSON.stringify({ title, summary, sequence: Number(sequence) }),
      });
      if (created.status !== "approved") {
        await confirmResource(
          `/projects/${projectId}/arcs/${created.id}/submit`,
          `/projects/${projectId}/arcs/${created.id}/approve`,
          projectId,
        );
      }
      await tryAdvancePipeline(projectId);
      setOk(`故事弧「${created.title}」已添加并确认。`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "添加并确认失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(arcId: string) {
    setBusyId(arcId);
    setError(null);
    try {
      await confirmResource(
        `/projects/${projectId}/arcs/${arcId}/submit`,
        `/projects/${projectId}/arcs/${arcId}/approve`,
        projectId,
      );
      await tryAdvancePipeline(projectId);
      setOk("故事弧已确认。");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "确认失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="max-w-3xl space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">故事弧</h1>
          <p className="text-sm text-muted-foreground">资料库 · 添加时默认一并确认</p>
        </div>
        <Link href={`/projects/${projectId}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
          回概览
        </Link>
      </div>
      <StatusBanner loading={loading} error={error} ok={ok} />
      {items.map((item) => (
        <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm">
          <div>
            {item.sequence}. {item.title} — {item.summary}
            <div className="text-xs text-muted-foreground">{approvalStatusLabel(item.status)}</div>
          </div>
          {item.status !== "approved" ? (
            <Button size="sm" variant="outline" disabled={busyId === item.id} onClick={() => void confirm(item.id)}>
              {busyId === item.id ? "确认中…" : "确认"}
            </Button>
          ) : null}
        </div>
      ))}
      <Field label="标题" value={title} onChange={setTitle} />
      <Field label="序号" value={sequence} onChange={setSequence} />
      <Field label="摘要" value={summary} onChange={setSummary} multiline />
      <Button disabled={busy} onClick={() => void createAndConfirm()}>
        {busy ? "处理中…" : "添加并确认"}
      </Button>
    </section>
  );
}

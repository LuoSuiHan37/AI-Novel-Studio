"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { confirmResource, tryAdvancePipeline } from "@/lib/hitl";
import { approvalStatusLabel } from "@/lib/labels";
import type { MasterPlot } from "@/lib/types";
import { cn } from "@/lib/utils";

type Architecture = {
  title: string;
  structure: string;
  summary: string;
  beats: { name: string; description: string; chapter_hint?: number | null }[];
  arcs: {
    title: string;
    sequence: number;
    summary: string;
    start_chapter_number: number;
    end_chapter_number: number;
  }[];
};

export default function PlotPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [title, setTitle] = useState("Rejected Luna");
  const [summary, setSummary] = useState("Rejection, exile, hidden identity, return.");
  const [beats, setBeats] = useState("Rejection|Pack Hall\nExile|Forest\nReturn|Challenge");
  const [status, setStatus] = useState("draft");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [architecture, setArchitecture] = useState<Architecture | null>(null);

  useEffect(() => {
    api<MasterPlot>(`/projects/${projectId}/plot`)
      .then((plot) => {
        setTitle(plot.title);
        setSummary(plot.summary);
        setStatus(plot.status);
        setBeats(plot.beats.map((item) => `${item.name}|${item.description}`).join("\n"));
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [projectId]);

  async function saveAndConfirm() {
    setBusy(true);
    setError(null);
    try {
      const saved = await api<MasterPlot>(`/projects/${projectId}/plot`, {
        method: "PATCH",
        projectId,
        body: JSON.stringify({
          title,
          summary,
          beats: beats
            .split("\n")
            .map((line) => line.split("|"))
            .filter((parts) => parts[0]?.trim())
            .map(([name, description]) => ({ name: name.trim(), description: (description || "").trim() })),
        }),
      });
      setStatus(saved.status);
      if (saved.status !== "approved") {
        await confirmResource(`/projects/${projectId}/plot/submit`, `/projects/${projectId}/plot/approve`, projectId);
        const plot = await api<MasterPlot>(`/projects/${projectId}/plot`);
        setStatus(plot.status);
      }
      await tryAdvancePipeline(projectId);
      setOk("主线情节已保存，已自动确定。可回概览看下一步。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function suggestArchitecture() {
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const proposal = await api<Architecture>(`/projects/${projectId}/architecture-suggestion`, {
        method: "POST",
        projectId,
      });
      setArchitecture(proposal);
      setOk("整书架构已生成预览；确认无误后再应用。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "生成整书架构失败");
    } finally {
      setBusy(false);
    }
  }

  async function applyArchitecture() {
    if (!architecture) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/projects/${projectId}/architecture/apply`, {
        method: "POST",
        projectId,
        body: JSON.stringify(architecture),
      });
      setTitle(architecture.title);
      setSummary(architecture.summary);
      setBeats(architecture.beats.map((item) => `${item.name}|${item.description}`).join("\n"));
      setArchitecture(null);
      setOk("整书架构已应用。故事弧已按序号更新或新增，旧的多余故事弧会保留待人工处理。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "应用整书架构失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-3xl space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">主线情节</h1>
          <p className="text-sm text-muted-foreground">状态：{approvalStatusLabel(status)} · 点一次即可过门禁</p>
        </div>
        <Link href={`/projects/${projectId}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
          回概览
        </Link>
      </div>
      <StatusBanner loading={loading} error={error} ok={ok} />
      <div className="rounded-lg border border-border/70 bg-muted/30 p-3 space-y-2">
        <div>
          <p className="font-medium">整书架构助手</p>
          <p className="text-sm text-muted-foreground">基于故事圣经、世界观和角色生成全书主线与故事弧；生成后先预览，不会自动覆盖。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy} onClick={() => void suggestArchitecture()}>
            {busy ? "处理中…" : "生成整书架构预览"}
          </Button>
          {architecture ? <Button disabled={busy} onClick={() => void applyArchitecture()}>确认并应用</Button> : null}
        </div>
        {architecture ? (
          <div className="space-y-2 rounded-md border border-border/70 bg-background p-3 text-sm">
            <p><span className="font-medium">{architecture.title}</span> · {architecture.structure}</p>
            <p>{architecture.summary}</p>
            <p className="font-medium">节拍：{architecture.beats.length} · 故事弧：{architecture.arcs.length}</p>
            <ul className="list-disc pl-5 text-muted-foreground">
              {architecture.arcs.map((arc) => <li key={`${arc.sequence}-${arc.title}`}>第 {arc.sequence} 弧：{arc.title}（{arc.start_chapter_number}-{arc.end_chapter_number} 章）</li>)}
            </ul>
          </div>
        ) : null}
      </div>
      <Field label="标题" value={title} onChange={setTitle} />
      <Field label="摘要" value={summary} onChange={setSummary} multiline />
      <Field label="节拍（每行：名称|描述，至少 3 条）" value={beats} onChange={setBeats} multiline rows={6} />
      <Button disabled={busy} onClick={() => void saveAndConfirm()}>
        {busy ? "保存中…" : "保存"}
      </Button>
    </section>
  );
}

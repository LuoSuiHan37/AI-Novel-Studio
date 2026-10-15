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
      <p className="text-sm text-muted-foreground">整书框架只能在“创建新书”流程中，由已确认的创作提案生成并确认；本页只负责查看和编辑已落地的主线。</p>
      <Field label="标题" value={title} onChange={setTitle} />
      <Field label="摘要" value={summary} onChange={setSummary} multiline />
      <Field label="节拍（每行：名称|描述，至少 3 条）" value={beats} onChange={setBeats} multiline rows={6} />
      <Button disabled={busy} onClick={() => void saveAndConfirm()}>
        {busy ? "保存中…" : "保存"}
      </Button>
    </section>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { confirmResource, tryAdvancePipeline } from "@/lib/hitl";
import { approvalStatusLabel } from "@/lib/labels";
import type { MasterPlot, PlotBeat } from "@/lib/types";
import { cn } from "@/lib/utils";

const emptyBeat = (): PlotBeat => ({ name: "", description: "", chapter_hint: null, beat_type: "plot", reader_belief: "", truth: "", emotional_shock: "", setup: "", payoff: "" });
const typeLabel: Record<string, string> = { reversal: "反转", shock: "情绪震点", plot: "普通推进" };

export default function PlotPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [title, setTitle] = useState("Rejected Luna");
  const [summary, setSummary] = useState("Rejection, exile, hidden identity, return.");
  const [beatDrafts, setBeatDrafts] = useState<PlotBeat[]>([emptyBeat(), emptyBeat(), emptyBeat()]);
  const [status, setStatus] = useState("draft");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<MasterPlot>(`/projects/${projectId}/plot`).then((plot) => {
      setTitle(plot.title); setSummary(plot.summary); setStatus(plot.status);
      setBeatDrafts(plot.beats.length ? plot.beats.map((beat) => ({ ...emptyBeat(), ...beat })) : [emptyBeat()]);
    }).catch(() => undefined).finally(() => setLoading(false));
  }, [projectId]);

  const reversalCount = beatDrafts.filter((beat) => beat.beat_type === "reversal").length;
  const shockCount = beatDrafts.filter((beat) => beat.beat_type === "shock").length;
  const rhythmMessage = reversalCount >= 3 && shockCount >= 4 ? "三番四震节点已覆盖" : `建议至少安排 3 个反转、4 个情绪震点（当前 ${reversalCount} / ${shockCount}）`;
  const timeline = useMemo(() => [...beatDrafts].filter((beat) => beat.name.trim() || beat.description.trim()).sort((a, b) => (a.chapter_hint ?? 9999) - (b.chapter_hint ?? 9999)), [beatDrafts]);

  function updateBeat(index: number, patch: Partial<PlotBeat>) { setBeatDrafts((current) => current.map((beat, itemIndex) => itemIndex === index ? { ...beat, ...patch } : beat)); }

  async function saveAndConfirm() {
    setBusy(true); setError(null);
    try {
      const saved = await api<MasterPlot>(`/projects/${projectId}/plot`, { method: "PATCH", projectId, body: JSON.stringify({ title, summary, beats: beatDrafts.filter((beat) => beat.name.trim() || beat.description.trim()).map((beat) => ({ ...beat, name: beat.name.trim(), description: beat.description.trim() })) }) });
      setStatus(saved.status); setBeatDrafts(saved.beats.map((beat) => ({ ...emptyBeat(), ...beat })));
      if (saved.status !== "approved") { await confirmResource(`/projects/${projectId}/plot/submit`, `/projects/${projectId}/plot/approve`, projectId); const plot = await api<MasterPlot>(`/projects/${projectId}/plot`); setStatus(plot.status); }
      await tryAdvancePipeline(projectId); setOk("主线情节已保存，三番四震节点会继续传递到章节计划。");
    } catch (err) { setError(err instanceof ApiError ? err.message : "保存失败"); } finally { setBusy(false); }
  }

  return <section className="max-w-5xl space-y-4">
    <div className="flex flex-wrap items-end justify-between gap-2"><div><h1 className="text-2xl font-semibold">主线情节</h1><p className="text-sm text-muted-foreground">状态：{approvalStatusLabel(status)} · 点一次即可过门禁</p></div><Link href={`/projects/${projectId}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>回概览</Link></div>
    <StatusBanner loading={loading} error={error} ok={ok} />
    <p className="text-sm text-muted-foreground">整书框架由创作提案生成；本页可查看和调整反转、情绪震点及其章节位置。</p>
    <Field label="标题" value={title} onChange={setTitle} /><Field label="摘要" value={summary} onChange={setSummary} multiline />
    <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-semibold text-slate-800">三番四震时间线</p><p className="mt-1 text-xs text-slate-500">反转改变读者认知，震点负责制造情绪冲击；普通节点负责铺垫和回收。</p></div><span className={cn("rounded-full px-3 py-1 text-xs font-medium", reversalCount >= 3 && shockCount >= 4 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>{rhythmMessage}</span></div><div className="mt-4 space-y-2">{timeline.length ? timeline.map((beat, index) => <div key={`${beat.name}-${index}`} className="flex items-start gap-3 rounded-lg bg-white/80 px-3 py-2 text-sm"><span className="mt-0.5 min-w-12 text-xs font-semibold text-blue-600">{beat.chapter_hint ? `第${beat.chapter_hint}章` : "待安排"}</span><span className="min-w-20 rounded-full bg-slate-100 px-2 py-0.5 text-center text-xs text-slate-600">{typeLabel[beat.beat_type || "plot"] || beat.beat_type}</span><span className="font-medium text-slate-800">{beat.name || "未命名节点"}</span><span className="truncate text-slate-500">{beat.description}</span></div>) : <p className="text-sm text-slate-500">还没有可展示的节点。</p>}</div></div>
    <div className="space-y-3">{beatDrafts.map((beat, index) => <div key={index} className="rounded-xl border bg-card p-4 shadow-sm"><div className="grid gap-3 md:grid-cols-[1fr_150px_110px]"><Field label={`节点 ${index + 1} 名称`} value={beat.name} onChange={(value) => updateBeat(index, { name: value })} /><label className="space-y-1 text-sm"><span className="text-muted-foreground">类型</span><select className="h-10 w-full rounded-md border bg-background px-3" value={beat.beat_type || "plot"} onChange={(event) => updateBeat(index, { beat_type: event.target.value })}><option value="plot">普通推进</option><option value="reversal">反转</option><option value="shock">情绪震点</option></select></label><Field label="章节" value={beat.chapter_hint ? String(beat.chapter_hint) : ""} onChange={(value) => updateBeat(index, { chapter_hint: Number(value) || null })} /></div><div className="mt-3 grid gap-3 md:grid-cols-2"><Field label="事件描述" value={beat.description} onChange={(value) => updateBeat(index, { description: value })} multiline /><Field label="情绪冲击" value={beat.emotional_shock || ""} onChange={(value) => updateBeat(index, { emotional_shock: value })} multiline /></div>{beat.beat_type === "reversal" ? <div className="mt-3 grid gap-3 md:grid-cols-2"><Field label="读者原本以为" value={beat.reader_belief || ""} onChange={(value) => updateBeat(index, { reader_belief: value })} multiline /><Field label="真实情况" value={beat.truth || ""} onChange={(value) => updateBeat(index, { truth: value })} multiline /><Field label="前置伏笔" value={beat.setup || ""} onChange={(value) => updateBeat(index, { setup: value })} multiline /><Field label="后续回收" value={beat.payoff || ""} onChange={(value) => updateBeat(index, { payoff: value })} multiline /></div> : null}</div>)}</div>
    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={() => setBeatDrafts((current) => [...current, emptyBeat()])}>添加节点</Button><Button disabled={busy} onClick={() => void saveAndConfirm()}>{busy ? "保存中…" : "保存并确认"}</Button></div>
  </section>;
}

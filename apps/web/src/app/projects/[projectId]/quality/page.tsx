"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Lightbulb, ShieldCheck, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type Finding = { severity: string; category: string; location: string; problem: string; why_it_matters: string; recommendation: string };
type Review = { review_type: string; overall: string; score?: number; findings?: Finding[]; can_start_chapter_generation?: boolean; overall_notes?: string; prompt_version?: string; status?: string; chapter_number?: number };
type OptimizationCluster = { owner: string; category: string; count: number; chapters: number[]; recommendation: string; examples: Array<{ message: string; evidence: string }> };
type OptimizationReport = { total_signals: number; clusters: OptimizationCluster[] };

const ownerLabel: Record<string, string> = { writer_prompt: "Writer Prompt", chapter_plan: "章节计划", review_prompt: "审核 Prompt", unknown: "待判断" };

export default function QualityPage({ params }: { params: { projectId: string } }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [optimization, setOptimization] = useState<OptimizationReport>({ total_signals: 0, clusters: [] });
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const load = async () => {
    try {
      const [reviewRows, report] = await Promise.all([
        api<Review[]>(`/projects/${params.projectId}/reviews`),
        api<OptimizationReport>(`/projects/${params.projectId}/reviews/optimization`),
      ]);
      setReviews(reviewRows); setOptimization(report);
    } catch (err) { setError(err instanceof Error ? err.message : "加载质量记录失败"); }
  };
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [params.projectId]);
  const run = async () => { setBusy(true); setError(""); setMessage(""); try { await api(`/projects/${params.projectId}/reviews/project`, { method: "POST", projectId: params.projectId, body: "{}" }); setMessage("系统项目审核已完成。"); await load(); } catch (err) { setError(err instanceof Error ? err.message : "系统审核失败"); } finally { setBusy(false); } };
  const latest = reviews.filter((item) => item.review_type === "project_independent").at(-1);
  return <div className="mx-auto w-full max-w-[1120px] pb-12">
    <header className="flex min-h-[72px] items-center justify-between border-b border-[#e4eaf3]"><div><p className="text-sm text-[#7d8aa1]">作品 / 质量中心</p><h1 className="mt-1 font-serif text-[30px] font-semibold text-[#101c3b]">系统审核与提示词优化</h1></div><Button className="bg-[#2563eb] hover:bg-[#1d4ed8]" onClick={() => void run()} disabled={busy}>{busy ? "审核中…" : "运行项目审核"}</Button></header>
    <div className="space-y-5 pt-8">
      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div>}
      <section className="rounded-xl border border-[#e2e8f1] bg-white p-6 shadow-sm"><div className="flex items-start gap-4"><div className="rounded-xl bg-[#edf3ff] p-3 text-[#2563eb]"><ShieldCheck className="size-6" /></div><div><h2 className="text-lg font-bold text-[#172443]">项目系统审核</h2><p className="mt-1 text-sm leading-6 text-[#718099]">审核 Story Bible、世界观、角色、主线和章节计划是否具备进入正文生产的条件。</p></div></div>{latest ? <div className="mt-6 space-y-4"><div className="flex flex-wrap items-center gap-3"><span className={`rounded-full px-3 py-1 text-xs font-semibold ${latest.overall === "BLOCKED" ? "bg-red-50 text-red-700" : latest.can_start_chapter_generation ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{latest.overall}</span><span className="text-sm text-[#718099]">评分 {latest.score}/10</span>{latest.prompt_version && <span className="text-xs text-[#9aa6b8]">Prompt {latest.prompt_version}</span>}</div><p className="text-sm leading-6 text-[#52627d]">{latest.overall_notes || "审核已完成。"}</p>{latest.findings?.length ? <div className="space-y-3">{latest.findings.map((finding, index) => <div key={`${finding.location}-${index}`} className="rounded-lg border border-[#edf1f6] p-4"><div className="flex items-center gap-2 text-sm font-semibold text-[#25365a]">{finding.severity === "ERROR" ? <XCircle className="size-4 text-red-500" /> : finding.severity === "WARNING" ? <AlertTriangle className="size-4 text-amber-500" /> : <CheckCircle2 className="size-4 text-emerald-500" />}{finding.problem}</div><p className="mt-2 text-xs leading-5 text-[#718099]">位置：{finding.location} · {finding.why_it_matters}</p><p className="mt-1 text-xs leading-5 text-[#52627d]">建议：{finding.recommendation}</p></div>)}</div> : <p className="text-sm text-[#718099]">未发现结构性问题。</p>}</div> : <div className="mt-6 rounded-lg border border-dashed border-[#dbe3ef] p-6 text-center text-sm text-[#8995a9]">尚未运行系统审核。</div>}</section>
      <section className="rounded-xl border border-[#e2e8f1] bg-white p-6 shadow-sm"><div className="flex items-start justify-between gap-4"><div><h2 className="flex items-center gap-2 text-lg font-bold text-[#172443]"><Lightbulb className="size-5 text-[#d18a18]" />提示词优化信号</h2><p className="mt-1 text-sm leading-6 text-[#718099]">来自真实章节生成和审核结果的重复问题。系统只提供证据和建议，不会自动覆盖 Prompt。</p></div><span className="rounded-full bg-[#fff7df] px-3 py-1 text-xs font-semibold text-[#a66a00]">{optimization.total_signals} 条信号</span></div>{optimization.clusters.length ? <div className="mt-5 space-y-3">{optimization.clusters.map((cluster) => <div key={`${cluster.owner}-${cluster.category}`} className="rounded-lg border border-[#edf1f6] p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><span className="rounded-full bg-[#edf3ff] px-2.5 py-1 text-xs font-semibold text-[#2563eb]">{ownerLabel[cluster.owner] || cluster.owner}</span><strong className="text-sm text-[#25365a]">{cluster.category}</strong></div><span className="text-xs text-[#9aa6b8]">出现 {cluster.count} 次 · {cluster.chapters.length ? `第 ${cluster.chapters.join("、")} 章` : "项目级"}</span></div><p className="mt-3 text-sm leading-6 text-[#52627d]">{cluster.recommendation}</p>{cluster.examples.slice(0, 2).map((example, index) => <p key={index} className="mt-2 rounded-md bg-[#f7f9fc] px-3 py-2 text-xs leading-5 text-[#718099]">证据：{example.evidence || example.message}</p>)}</div>)}</div> : <div className="mt-5 rounded-lg border border-dashed border-[#dbe3ef] p-6 text-center text-sm text-[#8995a9]">还没有足够的真实章节信号。完成章节生成和审核后，这里会自动聚合高频问题。</div>}</section>
      <section className="rounded-xl border border-[#e2e8f1] bg-white p-6 shadow-sm"><h2 className="text-lg font-bold text-[#172443]">审核记录</h2><div className="mt-4 space-y-2">{reviews.length ? reviews.slice().reverse().map((review, index) => <div key={`${review.review_type}-${index}`} className="flex items-center justify-between rounded-lg bg-[#f7f9fc] px-4 py-3 text-sm"><span className="text-[#52627d]">{review.review_type === "project_independent" ? "项目系统审核" : review.chapter_number ? `第 ${review.chapter_number} 章系统审核` : "章节系统审核"}</span><span className="font-semibold text-[#25365a]">{review.overall || review.status}</span></div>) : <p className="text-sm text-[#8995a9]">暂无审核记录。</p>}</div></section>
    </div>
  </div>;
}

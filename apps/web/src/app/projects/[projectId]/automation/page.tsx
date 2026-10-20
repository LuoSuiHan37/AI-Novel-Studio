"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Bell, Check, Clock3, Play, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";

type Schedule = { enabled: boolean; interval_minutes: number; max_attempts: number; platforms: string[]; next_run_at?: string | null } | null;
type Task = { id: string; task_type: string; status: string; current_stage?: string; progress_message?: string | null; chapter_number?: number | null; attempt_count: number; created_at: string; started_at?: string | null; finished_at?: string | null; heartbeat_at?: string | null; error_message?: string | null };
type PublishTask = { id: string; platform: string; status: string; current_stage?: string; progress_message?: string | null; chapter_id: string; error_message?: string | null; started_at?: string | null; finished_at?: string | null; heartbeat_at?: string | null };
type Notification = { id: string; message: string; read_at?: string | null; created_at: string; details?: { guidance?: string; error?: string; stage?: string } | null };
type Binding = { platform?: string | null; platform_book_id?: string | null; platform_book_title?: string | null } | null;
type AutoSettings = { auto_publish_enabled: boolean; completed: boolean; target_chapter_count?: number | null; local_chapter_count: number; platform_chapter_count?: number | null; daily_limit: number; published_today: number; platform?: string | null } | null;

const platforms = [["fanqie", "番茄小说"], ["qidian", "起点中文网"], ["qimao", "七猫小说"]] as const;
const stageLabels: Record<string, string> = { queued: "排队等待", recovering: "服务恢复中", generating: "正在生成正文", reviewing: "正在审核正文", uploading_draft: "正在上传平台草稿", waiting_upload: "等待上传", waiting_publish: "等待正式发布", publishing: "正在正式发布", published: "发布成功", completed: "全部完成", needs_human_review: "等待人工处理", failed: "执行失败", publish_failed: "正式发布失败", quota_reached: "今日额度已用完" };
function stageLabel(stage?: string, status?: string) { return stageLabels[stage || status || ""] || stage || status || "未知状态"; }

export default function AutomationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [schedule, setSchedule] = useState<Schedule>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [publishTasks, setPublishTasks] = useState<PublishTask[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [binding, setBinding] = useState<Binding>(null);
  const [autoSettings, setAutoSettings] = useState<AutoSettings>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [loadedSchedule, loadedTasks, loadedPublishTasks, loadedNotifications, loadedBinding, loadedSettings] = await Promise.all([
      api<Schedule>(`/projects/${projectId}/automation/schedule`).catch(() => null),
      api<Task[]>(`/projects/${projectId}/automation/tasks`),
      api<PublishTask[]>(`/projects/${projectId}/automation/publish-tasks`),
      api<Notification[]>(`/projects/${projectId}/automation/notifications`),
      api<Binding>(`/projects/${projectId}/automation/platform-binding`),
      api<AutoSettings>(`/projects/${projectId}/automation/settings`),
    ]);
    setSchedule(loadedSchedule ? { ...loadedSchedule, interval_minutes: 20 } : { enabled: false, interval_minutes: 20, max_attempts: 2, platforms: [] });
    setTasks(loadedTasks);
    setPublishTasks(loadedPublishTasks);
    setNotifications(loadedNotifications);
    setBinding(loadedBinding);
    setAutoSettings(loadedSettings);
  }

  useEffect(() => {
    let active = true;
    const refresh = () => { if (active) void load().catch((err) => setError(err instanceof ApiError ? err.message : "自动连载状态加载失败")); };
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [projectId]);

  function updateSchedule(patch: Partial<NonNullable<Schedule>>) {
    setSchedule((current) => ({ enabled: false, max_attempts: 2, platforms: [], ...current, ...patch, interval_minutes: 20 }));
  }

  async function saveSchedule() {
    if (!schedule) return;
    setBusy(true); setError(null); setMessage(null);
    try { await api(`/projects/${projectId}/automation/schedule`, { method: "PUT", projectId, body: JSON.stringify(schedule) }); setMessage("自动连载设置已保存"); await load(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "保存自动连载设置失败"); }
    finally { setBusy(false); }
  }

  async function saveBinding() {
    if (!binding?.platform_book_id?.trim()) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      const saved = await api<Binding>(`/projects/${projectId}/automation/platform-binding`, { method: "PUT", projectId, body: JSON.stringify({ platform_book_id: binding.platform_book_id.trim(), platform_book_title: binding.platform_book_title?.trim() || null }) });
      setBinding(saved); setMessage("平台书籍绑定已保存"); await load();
    } catch (err) { setError(err instanceof ApiError ? err.message : "保存平台书籍绑定失败"); }
    finally { setBusy(false); }
  }

  async function toggleAutoPublish(enabled: boolean) {
    setBusy(true); setError(null); setMessage(null);
    try {
      const saved = await api<AutoSettings>(`/projects/${projectId}/automation/settings`, { method: "PUT", projectId, body: JSON.stringify({ auto_publish_enabled: enabled }) });
      setAutoSettings((current) => ({
        auto_publish_enabled: enabled,
        completed: current?.completed ?? saved?.completed ?? false,
        target_chapter_count: current?.target_chapter_count ?? saved?.target_chapter_count ?? null,
        local_chapter_count: current?.local_chapter_count ?? saved?.local_chapter_count ?? 0,
        platform_chapter_count: current?.platform_chapter_count ?? saved?.platform_chapter_count ?? null,
        daily_limit: current?.daily_limit ?? saved?.daily_limit ?? 4,
        published_today: current?.published_today ?? saved?.published_today ?? 0,
        platform: current?.platform ?? saved?.platform ?? null,
      }));
      setMessage(enabled ? "自动正式发布已开启" : "自动正式发布已关闭");
      await load();
    } catch (err) { setError(err instanceof ApiError ? err.message : "更新自动正式发布设置失败"); }
    finally { setBusy(false); }
  }

  async function runNow() {
    setBusy(true); setError(null); setMessage(null);
    try { await api(`/projects/${projectId}/automation/enqueue-next`, { method: "POST", projectId, body: JSON.stringify({ max_attempts: schedule?.max_attempts || 2 }) }); setMessage("下一章已加入生成队列"); await load(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "立即生成失败"); }
    finally { setBusy(false); }
  }

  async function confirmPublish(taskId: string) {
    setBusy(true); setError(null); setMessage(null);
    try { await api(`/projects/${projectId}/automation/publish-tasks/${taskId}/confirm`, { method: "POST", projectId, body: JSON.stringify({ confirmed_by: "studio-user" }) }); setMessage("已确认并提交正式发布"); await load(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "发布确认失败"); }
    finally { setBusy(false); }
  }

  async function markRead(id: string) {
    await api(`/projects/${projectId}/automation/notifications/${id}/read`, { method: "POST", projectId });
    setNotifications((items) => items.map((item) => item.id === id ? { ...item, read_at: new Date().toISOString() } : item));
  }

  const targetPlatform = binding?.platform || schedule?.platforms?.[0] || "";
  const targetPlatformLabel = platforms.find(([id]) => id === targetPlatform)?.[1] || targetPlatform || "未设置";
  return <div className="mx-auto max-w-[1180px] space-y-6 pb-12">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border/70 py-6"><div><Link href={`/projects/${projectId}/chapters`} className="text-sm text-muted-foreground hover:text-primary">← 返回章节目录</Link><h1 className="mt-2 text-3xl font-semibold">自动连载</h1><p className="mt-1 text-sm text-muted-foreground">管理自动生成、平台草稿和正式发布确认。</p></div><Button onClick={() => void runNow()} disabled={busy}><Play className="size-4" />立即生成下一章</Button></header>
    <StatusBanner loading={false} error={error} ok={message} />
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-lg font-semibold text-amber-950">自动正式发布</h2><p className="mt-1 text-sm leading-6 text-amber-900/80">开启后，系统每天自动生成并正式发布，最多 4 章；平台出现 AI 内容确认时会自动选择“是”。</p><p className="mt-2 text-xs text-amber-900/70">今日已发布：{autoSettings?.published_today || 0} / {autoSettings?.daily_limit || 4} 章 · 本地：{autoSettings?.local_chapter_count || 0} / {autoSettings?.target_chapter_count || "—"} 章</p></div><label className="flex items-center gap-3 rounded-full bg-white px-4 py-3 text-sm font-medium text-amber-950 shadow-sm"><input type="checkbox" checked={autoSettings?.auto_publish_enabled || false} onChange={(e) => void toggleAutoPublish(e.target.checked)} disabled={busy || autoSettings?.completed} />{autoSettings?.auto_publish_enabled ? "已开启" : "未开启"}</label></div></section>
    <section className="rounded-2xl border border-border/70 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">平台作品绑定</h2><p className="mt-1 text-sm text-muted-foreground">自动上传只发送到作品的平台标记，必须先绑定该平台的书籍 ID。</p><div className="mt-4 grid gap-4 md:grid-cols-3"><div className="rounded-lg bg-slate-50 p-3 text-sm"><span className="text-muted-foreground">目标平台</span><strong className="mt-1 block">{targetPlatformLabel}</strong></div><label className="text-sm">平台书籍 ID<input className="mt-2 h-10 w-full rounded-lg border px-3" value={binding?.platform_book_id || ""} onChange={(e) => setBinding((current) => ({ ...(current || {}), platform_book_id: e.target.value }))} placeholder="例如：平台作品 ID" /></label><label className="text-sm">平台书名（可选）<input className="mt-2 h-10 w-full rounded-lg border px-3" value={binding?.platform_book_title || ""} onChange={(e) => setBinding((current) => ({ ...(current || {}), platform_book_title: e.target.value }))} placeholder="用于人工核对" /></label></div><Button className="mt-5" variant="outline" onClick={() => void saveBinding()} disabled={busy || !binding?.platform_book_id?.trim()}><Save className="size-4" />保存绑定</Button></section>
    <section className="rounded-2xl border border-border/70 bg-white p-6 shadow-sm"><div className="flex items-center justify-between"><div><h2 className="flex items-center gap-2 text-lg font-semibold"><Clock3 className="size-5 text-primary" />定时连载</h2><p className="mt-1 text-sm text-muted-foreground">系统固定每 20 分钟处理一章，平台自动使用上面的作品标记。</p></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={schedule?.enabled || false} onChange={(e) => updateSchedule({ enabled: e.target.checked })} />启用</label></div><div className="mt-5 grid gap-4 md:grid-cols-3"><div className="rounded-lg bg-slate-50 p-3 text-sm"><span className="text-muted-foreground">任务间隔</span><strong className="mt-1 block">固定 20 分钟</strong></div><label className="text-sm">失败重试次数<input className="mt-2 h-10 w-full rounded-lg border px-3" type="number" min={1} max={4} value={schedule?.max_attempts || 2} onChange={(e) => updateSchedule({ max_attempts: Number(e.target.value) })} /></label><div className="rounded-lg bg-slate-50 p-3 text-sm"><span className="text-muted-foreground">每日正式发布上限</span><strong className="mt-1 block">固定 4 章</strong></div></div><Button className="mt-5" variant="outline" onClick={() => void saveSchedule()} disabled={busy}><Save className="size-4" />保存设置</Button></section>
    <section className="rounded-2xl border border-border/70 bg-white p-6 shadow-sm"><div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold">生成任务历史</h2><p className="mt-1 text-xs text-muted-foreground">状态每 5 秒自动刷新，记录保存在数据库中，切换页面不会丢失。</p></div><span className="text-xs text-muted-foreground">共 {tasks.length} 条</span></div><div className="mt-4 divide-y">{tasks.length ? tasks.map((task) => <div key={task.id} className="space-y-2 py-4 text-sm"><div className="flex flex-wrap items-center justify-between gap-3"><span className="font-medium">第 {task.chapter_number || "—"} 章 · {task.task_type === "generate_next_chapter" ? "自动连载任务" : task.task_type}</span><span className={`rounded-full px-3 py-1 text-xs ${task.status === "failed" ? "bg-rose-100 text-rose-700" : task.status === "completed" ? "bg-emerald-100 text-emerald-700" : "bg-blue-100 text-blue-700"}`}>{stageLabel(task.current_stage, task.status)}</span></div><p className="text-slate-700">{task.progress_message || "等待后台处理"}</p><div className="flex flex-wrap gap-4 text-xs text-muted-foreground"><span>尝试 {task.attempt_count} 次</span>{task.started_at ? <span>开始：{new Date(task.started_at).toLocaleString()}</span> : null}{task.heartbeat_at ? <span>最近更新：{new Date(task.heartbeat_at).toLocaleTimeString()}</span> : null}</div>{task.error_message ? <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">失败原因：{task.error_message}</p> : null}</div>) : <p className="py-4 text-sm text-muted-foreground">暂无自动任务。</p>}</div></section>
    <section className="rounded-2xl border border-border/70 bg-white p-6 shadow-sm"><div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold">平台发布任务</h2><p className="mt-1 text-xs text-muted-foreground">上传、AI 确认和正式发布分别记录状态。</p></div><span className="text-xs text-muted-foreground">共 {publishTasks.length} 条</span></div><div className="mt-4 divide-y">{publishTasks.length ? publishTasks.map((task) => <div key={task.id} className="space-y-2 py-4 text-sm"><div className="flex flex-wrap items-center justify-between gap-3"><span className="font-medium">{platforms.find(([id]) => id === task.platform)?.[1] || task.platform}</span><span className="rounded-full bg-slate-100 px-3 py-1 text-xs">{stageLabel(task.current_stage, task.status)}</span></div><p className="text-slate-700">{task.progress_message || "等待上传"}</p><div className="flex flex-wrap items-center gap-2">{task.status === "awaiting_confirmation" ? <Button size="sm" disabled={busy} onClick={() => void confirmPublish(task.id)}><Check className="size-3" />确认发布</Button> : null}{task.error_message ? <p className="text-xs text-rose-600">失败原因：{task.error_message}</p> : null}</div></div>) : <p className="py-4 text-sm text-muted-foreground">暂无平台发布任务。</p>}</div></section>
    <section className="rounded-2xl border border-amber-200 bg-amber-50/50 p-6 shadow-sm"><h2 className="flex items-center gap-2 text-lg font-semibold text-amber-950"><Bell className="size-5 text-amber-600" />异常通知</h2><p className="mt-1 text-xs text-amber-900/70">每条通知都会说明失败原因和建议检查项；处理后可标记已读。</p><div className="mt-4 divide-y divide-amber-200">{notifications.length ? notifications.map((item) => <div key={item.id} className="flex items-start justify-between gap-4 py-4 text-sm"><div className="min-w-0"><p className={item.read_at ? "text-amber-900/70" : "font-medium text-amber-950"}>{item.message}</p>{item.details?.guidance ? <p className="mt-2 rounded-lg bg-white/80 px-3 py-2 text-xs leading-5 text-amber-900">建议检查：{item.details.guidance}</p> : null}{item.details?.error ? <details className="mt-2 text-xs text-amber-900/60"><summary className="cursor-pointer">查看技术错误</summary><p className="mt-1 break-words">{item.details.error}</p></details> : null}</div>{!item.read_at ? <Button size="sm" variant="ghost" onClick={() => void markRead(item.id)}>标记已读</Button> : null}</div>) : <p className="py-4 text-sm text-muted-foreground">暂无异常通知。</p>}</div></section>
  </div>;
}

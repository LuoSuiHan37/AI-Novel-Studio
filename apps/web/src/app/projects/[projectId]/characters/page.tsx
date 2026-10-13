"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { DEFAULT_CHARACTER } from "@/lib/defaults";
import { tryAdvancePipeline } from "@/lib/hitl";
import { approvalStatusLabel, characterRoleLabel } from "@/lib/labels";
import type { Character } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function CharactersPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [items, setItems] = useState<Character[]>([]);
  const [form, setForm] = useState({ ...DEFAULT_CHARACTER, name: "Aria" });
  const [aliasesText, setAliasesText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function load() {
    setItems(await api<Character[]>(`/projects/${projectId}/characters`));
  }

  useEffect(() => {
    load()
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  async function createAndConfirm() {
    setBusy(true);
    setError(null);
    try {
      const created = await api<Character>(`/projects/${projectId}/characters`, {
        method: "POST",
        projectId,
        body: JSON.stringify({
          ...form,
          aliases: aliasesText.split(/[，,]/).map((name) => name.trim()).filter(Boolean),
          tropes: form.tropes,
        }),
      });
      await tryAdvancePipeline(projectId);
      setOk(`角色 ${created.name} 已添加并自动确定。`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "添加并确认失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold">角色</h1>
            <p className="text-sm text-muted-foreground">资料库 · 添加时默认一并确认</p>
          </div>
          <Link href={`/projects/${projectId}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
            回概览
          </Link>
        </div>
        <StatusBanner loading={loading} error={error} ok={ok} />
        {items.map((item) => (
          <article key={item.id} className="rounded-lg border p-3 text-sm">
            <div className="font-medium">
              {item.name} · {characterRoleLabel(item.role)} · {item.status === "approved" ? approvalStatusLabel(item.status) : "自动确定"}
            </div>
            <p className="text-muted-foreground">{item.goal}</p>
            {item.aliases?.length ? (
              <p className="mt-1 text-xs text-muted-foreground">别名：{item.aliases.join("、")}</p>
            ) : null}
          </article>
        ))}
      </div>
      <div className="space-y-2">
        <Field label="姓名" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
        <Field label="别名（逗号分隔，可选）" value={aliasesText} onChange={setAliasesText} />
        <Field label="角色定位" value={form.role} onChange={(v) => setForm({ ...form, role: v })} />
        <Field label="性格" value={form.personality} onChange={(v) => setForm({ ...form, personality: v })} />
        <Field label="背景" value={form.background} onChange={(v) => setForm({ ...form, background: v })} multiline />
        <Field label="目标" value={form.goal} onChange={(v) => setForm({ ...form, goal: v })} />
        <Field label="秘密" value={form.secret} onChange={(v) => setForm({ ...form, secret: v })} />
        <Button disabled={busy} onClick={() => void createAndConfirm()}>
          {busy ? "处理中…" : "添加并确认"}
        </Button>
      </div>
    </section>
  );
}

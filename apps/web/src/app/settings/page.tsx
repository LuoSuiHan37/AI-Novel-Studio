"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { getGlobalLlmPrefs, getStoredLlmKey, setGlobalLlmPrefs, setStoredLlmKey } from "@/lib/api";
import { getProviderPreset, LLM_PROVIDER_PRESETS, resolvePresetModel } from "@/lib/llm-presets";

const selectCls =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50";

export default function SettingsPage() {
  const saved = getGlobalLlmPrefs();
  const initialProvider = getProviderPreset(saved?.provider || "deepseek").id;
  const [provider, setProvider] = useState<string>(initialProvider);
  const [model, setModel] = useState(resolvePresetModel(initialProvider, saved?.model));
  const [baseUrl, setBaseUrl] = useState(saved?.baseUrl || getProviderPreset(initialProvider).baseUrl);
  const [apiKey, setApiKey] = useState(getStoredLlmKey(initialProvider));
  const initialReviewProvider = getProviderPreset(saved?.reviewProvider || "openai").id;
  const [reviewProvider, setReviewProvider] = useState<string>(initialReviewProvider);
  const [reviewModel, setReviewModel] = useState(resolvePresetModel(initialReviewProvider, saved?.reviewModel));
  const [reviewBaseUrl, setReviewBaseUrl] = useState(saved?.reviewBaseUrl || getProviderPreset(initialReviewProvider).baseUrl);
  const [reviewApiKey, setReviewApiKey] = useState(getStoredLlmKey(initialReviewProvider));
  const [ok, setOk] = useState<string | null>(null);
  const preset = useMemo(() => getProviderPreset(provider), [provider]);
  const reviewPreset = useMemo(() => getProviderPreset(reviewProvider), [reviewProvider]);

  function applyProvider(next: string) {
    const nextPreset = getProviderPreset(next);
    setProvider(next);
    setModel(nextPreset.defaultModel);
    setBaseUrl(nextPreset.baseUrl);
    setApiKey(getStoredLlmKey(next));
    setOk(null);
  }

  function applyReviewProvider(next: string) {
    const nextPreset = getProviderPreset(next);
    setReviewProvider(next);
    setReviewModel(nextPreset.defaultModel);
    setReviewBaseUrl(nextPreset.baseUrl);
    setReviewApiKey(getStoredLlmKey(next));
    setOk(null);
  }

  function save() {
    if (provider === reviewProvider && model === reviewModel) {
      setOk("生成模型和审查模型不能相同，请选择不同的模型。");
      return;
    }
    setStoredLlmKey(apiKey.trim(), provider);
    setStoredLlmKey(reviewApiKey.trim(), reviewProvider);
    setGlobalLlmPrefs({
      provider,
      model,
      baseUrl: baseUrl.trim(),
      reviewProvider,
      reviewModel,
      reviewBaseUrl: reviewBaseUrl.trim(),
    });
    const cleared = [
      !apiKey.trim() ? "生成 API Key" : "",
      !reviewApiKey.trim() ? "审查 API Key" : "",
    ].filter(Boolean);
    setOk(
      `已保存：生成使用 ${preset.label} / ${model}，审查使用 ${reviewPreset.label} / ${reviewModel}。${
        cleared.length ? `${cleared.join("、")}已清除。` : "Key 已脱敏保存。"
      }`,
    );
  }

  return (
    <section className="max-w-xl space-y-3">
      <h1 className="text-2xl font-semibold">AI 设置</h1>
      <p className="text-sm text-muted-foreground">生成模型负责写作和局部修改；审查模型必须独立于生成模型。</p>
      <StatusBanner ok={ok} />
      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">提供商 Provider</span>
        <select className={selectCls} value={provider} onChange={(e) => applyProvider(e.target.value)}>
          {LLM_PROVIDER_PRESETS.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
      </label>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">模型 Model</span>
        <select className={selectCls} value={model} onChange={(e) => setModel(e.target.value)}>
          {preset.models.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
      </label>
      <Field label="Base URL（可留空使用默认）" value={baseUrl} onChange={setBaseUrl} />
      <Field label={`${preset.label} API Key`} value={apiKey} onChange={setApiKey} type="password" allowReveal />
      <div className="border-t pt-4" />
      <h2 className="text-lg font-semibold">审查模型</h2>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">审查提供商 Provider</span>
        <select className={selectCls} value={reviewProvider} onChange={(e) => applyReviewProvider(e.target.value)}>
          {LLM_PROVIDER_PRESETS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">审查模型 Model</span>
        <select className={selectCls} value={reviewModel} onChange={(e) => setReviewModel(e.target.value)}>
          {reviewPreset.models.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
      <Field label="审查 Base URL（可留空使用默认）" value={reviewBaseUrl} onChange={setReviewBaseUrl} />
      <Field label={`${reviewPreset.label} 审查 API Key`} value={reviewApiKey} onChange={setReviewApiKey} type="password" allowReveal />
      <p className="text-xs text-muted-foreground">两套 API Key 只保存在当前浏览器，并以密码形式显示；审查模型未配置时不会自动视为通过。</p>
      <Button onClick={save}>保存</Button>
    </section>
  );
}

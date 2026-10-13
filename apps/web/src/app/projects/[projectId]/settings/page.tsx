"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import {
  api,
  ApiError,
  getStoredLlmKey,
  setProjectLlmPrefs,
  setStoredLlmKey,
} from "@/lib/api";
import {
  getProviderPreset,
  LLM_PROVIDER_PRESETS,
  resolvePresetModel,
} from "@/lib/llm-presets";
import type { CreativeProfile, LlmSettings, Project } from "@/lib/types";

const selectCls =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50";
const textareaCls =
  "min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50";

const emptyProfile: CreativeProfile = {
  reader_promise: "",
  novel_constitution: {
    core_question: "",
    reader_promise: "",
    ending_direction: "",
    themes: [],
    hard_constraints: [],
    forbidden_treatments: [],
    motifs: [],
  },
  environment_bible: {
    geography: "",
    time_and_climate: "",
    sensory_palette: [],
    social_pressures: [],
    daily_life_details: [],
    recurring_locations: [],
    environmental_constraints: [],
    recurring_motifs: [],
  },
  character_dynamics: [],
  relationship_rules: [],
  literary_review_rubric: [],
  rhythm_controls: [],
  hard_constraints: [],
  chapter_requirements: [],
  anti_ai_rules: [],
  style_guide: "",
};

function lines(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function normalizeProfile(raw: unknown): CreativeProfile {
  const value = raw && typeof raw === "object" ? (raw as Record<string, any>) : {};
  const constitution = value.novel_constitution || {};
  const environment = value.environment_bible || {};
  return {
    ...emptyProfile,
    ...value,
    reader_promise: String(value.reader_promise || value.positioning || ""),
    novel_constitution: {
      ...emptyProfile.novel_constitution,
      ...constitution,
      themes: lines(constitution.themes),
      hard_constraints: lines(constitution.hard_constraints),
      forbidden_treatments: lines(constitution.forbidden_treatments),
      motifs: lines(constitution.motifs),
    },
    environment_bible: {
      ...emptyProfile.environment_bible,
      ...environment,
      sensory_palette: lines(environment.sensory_palette),
      social_pressures: lines(environment.social_pressures),
      daily_life_details: lines(environment.daily_life_details),
      recurring_locations: lines(environment.recurring_locations),
      environmental_constraints: lines(environment.environmental_constraints),
      recurring_motifs: lines(environment.recurring_motifs),
    },
    character_dynamics: lines(value.character_dynamics),
    relationship_rules: lines(value.relationship_rules),
    literary_review_rubric: lines(value.literary_review_rubric),
    rhythm_controls: lines(value.rhythm_controls),
    hard_constraints: lines(value.hard_constraints),
    chapter_requirements: lines(value.chapter_requirements),
    anti_ai_rules: lines(value.anti_ai_rules),
    style_guide: String(value.style_guide || ""),
  };
}

function TextArea({ label, value, onChange, hint }: { label: string; value: string; onChange: (value: string) => void; hint?: string }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}
      <textarea className={textareaCls} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function LinesEditor({ label, values, onChange, hint }: { label: string; values: string[]; onChange: (values: string[]) => void; hint?: string }) {
  return (
    <TextArea
      label={label}
      hint={hint || "每行一条。"}
      value={values.join("\n")}
      onChange={(value) => onChange(value.split("\n").map((item) => item.trim()).filter(Boolean))}
    />
  );
}

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState("deepseek-chat");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com/v1");
  const [envName, setEnvName] = useState("DEEPSEEK_API_KEY");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<CreativeProfile>(emptyProfile);
  const [creativeSaving, setCreativeSaving] = useState(false);

  const preset = useMemo(() => getProviderPreset(provider), [provider]);

  useEffect(() => {
    Promise.all([api<LlmSettings>(`/projects/${projectId}/settings/llm`), api<Project>(`/projects/${projectId}`)])
      .then(([row, project]) => {
        const nextProvider = row.provider || "deepseek";
        const nextPreset = getProviderPreset(nextProvider);
        const nextModel = resolvePresetModel(nextProvider, row.model);
        setProvider(nextProvider);
        setModel(nextModel);
        setBaseUrl(row.base_url || nextPreset.baseUrl);
        setEnvName(row.api_key_env_name || nextPreset.envName);
        setApiKey(getStoredLlmKey(nextProvider));
        setProjectLlmPrefs(projectId, {
          provider: nextProvider,
          model: nextModel,
          baseUrl: row.base_url || nextPreset.baseUrl,
        });
        const metadata = project.extra_metadata || {};
        setProfile(normalizeProfile(metadata.creative_profile));
      })
      .catch(() => {
        setApiKey(getStoredLlmKey("deepseek"));
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  function applyProvider(next: string) {
    const nextPreset = getProviderPreset(next);
    setProvider(next);
    setModel(nextPreset.defaultModel);
    setBaseUrl(nextPreset.baseUrl);
    setEnvName(nextPreset.envName);
    setApiKey(getStoredLlmKey(next));
    setOk(null);
  }

  async function saveCreativeProfile() {
    setError(null);
    setOk(null);
    setCreativeSaving(true);
    try {
      await api(`/projects/${projectId}`, {
        method: "PATCH",
        projectId,
        body: JSON.stringify({ creative_profile: profile }),
      });
      setOk("已保存书级创作内核。后续构思、规划、写作和审核会继承这些规则。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "创作内核保存失败");
    } finally {
      setCreativeSaving(false);
    }
  }

  async function save() {
    setError(null);
    setOk(null);
    try {
      await api(`/projects/${projectId}/settings/llm`, {
        method: "PATCH",
        projectId,
        body: JSON.stringify({
          provider,
          model,
          base_url: baseUrl.trim() || null,
          api_key_env_name: envName || null,
        }),
      });
      setStoredLlmKey(apiKey.trim(), provider);
      setProjectLlmPrefs(projectId, {
        provider,
        model,
        baseUrl: baseUrl.trim(),
      });
      setOk(
        `已保存：写作时将使用 ${preset.label} / ${model}。API Key 仅存在本浏览器，通过请求头发送，不会写入数据库。`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    }
  }

  return (
    <section className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">AI 设置</h1>
      <p className="text-sm text-muted-foreground">
        选择善于写小说的模型并填写对应 API Key，章节生成与编辑会按该配置调用。
      </p>
      <StatusBanner loading={loading} error={error} ok={ok} />

      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">提供商 Provider</span>
        <select
          className={selectCls}
          value={provider}
          onChange={(e) => applyProvider(e.target.value)}
        >
          {LLM_PROVIDER_PRESETS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-1">
        <span className="text-xs font-medium text-muted-foreground">模型 Model</span>
        <select
          className={selectCls}
          value={model}
          onChange={(e) => setModel(e.target.value)}
        >
          {preset.models.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>

      <Field label="Base URL（可留空使用默认）" value={baseUrl} onChange={setBaseUrl} />
      <Field label="服务端 Key 环境变量名" value={envName} onChange={setEnvName} />
      <Field
        label={`${preset.label} API Key（仅浏览器）`}
        value={apiKey}
        onChange={setApiKey}
      />
      <p className="text-xs text-muted-foreground">
        模型列表为各家当前较适合长篇网文/创意写作的固定选项；Key 按提供商分开保存。
      </p>
      <Button onClick={() => void save()}>保存</Button>

      <div className="border-t pt-6">
        <h2 className="text-xl font-semibold">书级创作内核</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          这里定义的是这一本小说的独立规则。AI 会把它注入大纲、章节计划、正文和文学审核，避免不同小说互相污染。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <TextArea label="核心问题" value={profile.novel_constitution.core_question} onChange={(value) => setProfile({ ...profile, novel_constitution: { ...profile.novel_constitution, core_question: value } })} hint="这本书最终要追问什么人生问题？" />
        <TextArea label="读者承诺" value={profile.reader_promise} onChange={(value) => setProfile({ ...profile, reader_promise: value, novel_constitution: { ...profile.novel_constitution, reader_promise: value } })} hint="读者为什么愿意一直读下去？" />
        <TextArea label="结局方向" value={profile.novel_constitution.ending_direction} onChange={(value) => setProfile({ ...profile, novel_constitution: { ...profile.novel_constitution, ending_direction: value } })} hint="不是完整结局，而是人物最终要完成的变化。" />
        <TextArea label="风格指南" value={profile.style_guide} onChange={(value) => setProfile({ ...profile, style_guide: value })} hint="叙述距离、句子节奏、对白潜台词、情绪表达等。" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <LinesEditor label="主题" values={profile.novel_constitution.themes} onChange={(values) => setProfile({ ...profile, novel_constitution: { ...profile.novel_constitution, themes: values } })} />
        <LinesEditor label="反复意象" values={profile.novel_constitution.motifs} onChange={(values) => setProfile({ ...profile, novel_constitution: { ...profile.novel_constitution, motifs: values } })} />
        <LinesEditor label="硬约束" values={profile.novel_constitution.hard_constraints} onChange={(values) => setProfile({ ...profile, novel_constitution: { ...profile.novel_constitution, hard_constraints: values }, hard_constraints: values })} />
        <LinesEditor label="禁止处理方式" values={profile.novel_constitution.forbidden_treatments} onChange={(values) => setProfile({ ...profile, novel_constitution: { ...profile.novel_constitution, forbidden_treatments: values } })} />
      </div>

      <div className="border-t pt-6">
        <h2 className="text-xl font-semibold">环境圣经</h2>
        <p className="mt-1 text-sm text-muted-foreground">环境必须能够制造压力、限制行动，并随着人物关系变化产生新的意义。</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <TextArea label="地理与空间" value={profile.environment_bible.geography} onChange={(value) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, geography: value } })} />
        <TextArea label="时间与气候" value={profile.environment_bible.time_and_climate} onChange={(value) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, time_and_climate: value } })} />
        <LinesEditor label="感官素材" values={profile.environment_bible.sensory_palette} onChange={(values) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, sensory_palette: values } })} />
        <LinesEditor label="社会压力" values={profile.environment_bible.social_pressures} onChange={(values) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, social_pressures: values } })} />
        <LinesEditor label="日常生活细节" values={profile.environment_bible.daily_life_details} onChange={(values) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, daily_life_details: values } })} />
        <LinesEditor label="反复出现的地点" values={profile.environment_bible.recurring_locations} onChange={(values) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, recurring_locations: values } })} />
        <LinesEditor label="环境限制" values={profile.environment_bible.environmental_constraints} onChange={(values) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, environmental_constraints: values } })} />
        <LinesEditor label="环境意象" values={profile.environment_bible.recurring_motifs} onChange={(values) => setProfile({ ...profile, environment_bible: { ...profile.environment_bible, recurring_motifs: values } })} />
      </div>

      <div className="border-t pt-6">
        <h2 className="text-xl font-semibold">人物与关系规则</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <LinesEditor label="人物动态要求" values={profile.character_dynamics} onChange={(values) => setProfile({ ...profile, character_dynamics: values })} hint="例如：人物当前欲望、误解、秘密、底线、改变代价。" />
        <LinesEditor label="关系规则" values={profile.relationship_rules} onChange={(values) => setProfile({ ...profile, relationship_rules: values })} hint="例如：权力差、情感债务、信任变化的证据。" />
        <LinesEditor label="章节要求" values={profile.chapter_requirements} onChange={(values) => setProfile({ ...profile, chapter_requirements: values })} />
        <LinesEditor label="节奏控制" values={profile.rhythm_controls} onChange={(values) => setProfile({ ...profile, rhythm_controls: values })} />
        <LinesEditor label="反 AI 规则" values={profile.anti_ai_rules} onChange={(values) => setProfile({ ...profile, anti_ai_rules: values })} />
        <LinesEditor label="文学审核标准" values={profile.literary_review_rubric} onChange={(values) => setProfile({ ...profile, literary_review_rubric: values })} />
      </div>
      <Button onClick={() => void saveCreativeProfile()} disabled={creativeSaving}>
        {creativeSaving ? "保存中…" : "保存书级创作内核"}
      </Button>
    </section>
  );
}

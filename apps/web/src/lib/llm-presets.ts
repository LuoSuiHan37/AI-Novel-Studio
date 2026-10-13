export type LlmProviderId =
  | "deepseek"
  | "gemini"
  | "grok"
  | "openai"
  | "anthropic";

export type LlmProviderPreset = {
  id: LlmProviderId;
  label: string;
  envName: string;
  baseUrl: string;
  models: { id: string; label: string }[];
  defaultModel: string;
};

/** 各家当前较适合长篇网文/创意写作的常用模型（固定列表，不可自定义）。 */
export const LLM_PROVIDER_PRESETS: LlmProviderPreset[] = [
  {
    id: "deepseek",
    label: "DeepSeek",
    envName: "DEEPSEEK_API_KEY",
    baseUrl: "https://api.deepseek.com/v1",
    defaultModel: "deepseek-chat",
    models: [
      { id: "deepseek-chat", label: "deepseek-chat · 网文续写主力" },
      { id: "deepseek-reasoner", label: "deepseek-reasoner · 伏笔/逻辑向" },
    ],
  },
  {
    id: "gemini",
    label: "Gemini",
    envName: "GEMINI_API_KEY",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta",
    defaultModel: "gemini-2.5-pro",
    models: [
      { id: "gemini-2.5-pro", label: "gemini-2.5-pro · 长篇上下文/修订" },
      { id: "gemini-2.0-flash", label: "gemini-2.0-flash · 快速起草" },
    ],
  },
  {
    id: "grok",
    label: "Grok (xAI)",
    envName: "GROK_API_KEY",
    baseUrl: "https://api.x.ai/v1",
    defaultModel: "grok-3",
    models: [
      { id: "grok-3", label: "grok-3 · 创意叙事" },
      { id: "grok-4", label: "grok-4 · 高品质散文" },
      { id: "grok-3-mini", label: "grok-3-mini · 高性价比草稿" },
    ],
  },
  {
    id: "openai",
    label: "OpenAI",
    envName: "OPENAI_API_KEY",
    baseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o",
    models: [
      { id: "gpt-4o", label: "gpt-4o · 大纲/结构执行" },
      { id: "gpt-4.1", label: "gpt-4.1 · 长文连贯" },
      { id: "gpt-4o-mini", label: "gpt-4o-mini · 轻量草稿" },
    ],
  },
  {
    id: "anthropic",
    label: "Anthropic",
    envName: "ANTHROPIC_API_KEY",
    baseUrl: "https://api.anthropic.com",
    defaultModel: "claude-sonnet-4-5",
    models: [
      { id: "claude-sonnet-4-5", label: "claude-sonnet-4-5 · 文笔/对白" },
      { id: "claude-opus-4-1", label: "claude-opus-4-1 · 顶级散文质感" },
      { id: "claude-3-5-haiku-latest", label: "claude-3-5-haiku · 快速改稿" },
    ],
  },
];

export function getProviderPreset(provider: string): LlmProviderPreset {
  return (
    LLM_PROVIDER_PRESETS.find((item) => item.id === provider) || LLM_PROVIDER_PRESETS[0]
  );
}

export function resolvePresetModel(provider: string, model: string | null | undefined): string {
  const preset = getProviderPreset(provider);
  if (model && preset.models.some((item) => item.id === model)) return model;
  return preset.defaultModel;
}

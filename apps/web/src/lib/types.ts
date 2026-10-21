export type Project = {
  id: string;
  title: string;
  genre: string;
  tropes: string[];
  target_platform: string | null;
  language: string;
  chapter_count_target?: number | null;
  status: string;
  current_stage: string;
  created_at?: string;
  updated_at?: string;
  logline?: string | null;
  extra_metadata?: Record<string, unknown>;
};

export type NovelAudit = {
  status: "passed" | "blocked";
  publishable: boolean;
  planned_chapter_count: number | null;
  actual_chapter_count: number;
  missing_chapters: number[];
  overflow_chapters: number[];
  empty_chapters: number[];
  unfinished_chapters: number[];
  missing_plans: number[];
  repetition_findings: Array<Record<string, unknown>>;
  relevance_findings: Array<Record<string, unknown>>;
  longitudinal_findings?: Array<Record<string, unknown>>;
  story_state_findings?: Array<Record<string, unknown>>;
  plot_thread_findings?: Array<Record<string, unknown>>;
  plot_thread_coverage?: { open_hooks: number; open_foreshadowings: number };
  memory_coverage?: { chapters_with_memory: number; approved_chapters: number };
  missing_architecture?: string[];
};

export type CreativeProfile = {
  schema_version?: string;
  reader_promise: string;
  novel_constitution: {
    core_question: string;
    reader_promise: string;
    ending_direction: string;
    themes: string[];
    hard_constraints: string[];
    forbidden_treatments: string[];
    motifs: string[];
  };
  environment_bible: {
    geography: string;
    time_and_climate: string;
    sensory_palette: string[];
    social_pressures: string[];
    daily_life_details: string[];
    recurring_locations: string[];
    environmental_constraints: string[];
    recurring_motifs: string[];
  };
  character_dynamics: string[];
  relationship_rules: string[];
  literary_review_rubric: string[];
  rhythm_controls: string[];
  hard_constraints: string[];
  chapter_requirements: string[];
  anti_ai_rules: string[];
  style_guide: string;
};

export type StoryBible = {
  id: string;
  project_id: string;
  premise: string;
  theme: string;
  tone: string;
  narrative_style: string;
  pov: string;
  tense: string;
  target_word_count: number;
  chapter_word_count: number;
  romance_level: string;
  violence_level: string;
  heat_level: string;
  tropes: string[];
  logline: string | null;
  synopsis: string | null;
  status: string;
  extra_metadata?: {
    fanqie_submission?: {
      target_reader?: string;
      reading_tags?: string[];
      content_tags?: string[];
      protagonist_names?: string[];
      work_tags?: Record<string, string[]>;
    };
  };
};

export type Character = {
  id: string;
  project_id: string;
  name: string;
  aliases: string[];
  role: string;
  personality: string;
  background: string;
  goal: string;
  motivation: string;
  fear: string;
  secret: string;
  strength: string;
  weakness: string;
  internal_conflict: string;
  external_conflict: string;
  speech_style: string;
  character_arc: string;
  species: string | null;
  rank: string | null;
  tropes: string[];
  status: string;
};

export type WorldRule = {
  id: string;
  name: string;
  category: string;
  description: string;
  is_hard_constraint: boolean;
};

export type WorldBible = {
  id: string;
  name: string;
  summary: string;
  geography: string | null;
  factions: string[];
  rules: WorldRule[];
  status: string;
};

export type PlotBeat = {
  name: string;
  description: string;
  chapter_hint: number | null;
  beat_type?: string;
  reader_belief?: string;
  truth?: string;
  emotional_shock?: string;
  setup?: string;
  payoff?: string;
};
export type MasterPlot = {
  id: string;
  title: string;
  structure: string;
  summary: string;
  beats: PlotBeat[];
  is_active: boolean;
  status: string;
};

export type StoryArc = {
  id: string;
  title: string;
  sequence: number;
  summary: string;
  arc_type: string;
  start_chapter_number: number | null;
  end_chapter_number: number | null;
  status: string;
};

export type Chapter = {
  id: string;
  project_id: string;
  chapter_number: number;
  title: string;
  status: string;
  content: string;
  word_count: number;
  created_at?: string;
  updated_at?: string;
  extra_metadata?: Record<string, unknown>;
};

export type ChapterPlan = {
  id: string;
  chapter_number: number;
  chapter_title: string;
  pov: string;
  location: string;
  characters: string[];
  chapter_goal: string;
  conflict: string;
  emotional_arc: string;
  new_information: string;
  reveal: string;
  foreshadowing: string;
  setup: string;
  payoff: string;
  cliffhanger: string;
  target_word_count?: number;
  target_word_min?: number;
  target_word_max?: number;
  status: string;
};

export type ChapterPlanSuggestion = Omit<ChapterPlan, "id" | "status"> & {
  scenes: Omit<ScenePlan, "id" | "chapter_plan_id">[];
};

export type ScenePlan = {
  id: string;
  scene_number: number;
  location: string;
  characters: string[];
  goal: string;
  conflict: string;
  turning_point: string;
  dialogue_goal: string;
  emotion: string;
  information_revealed: string;
  ending: string;
  target_word_count?: number;
  target_word_min?: number;
  target_word_max?: number;
};

export type Hook = {
  id: string;
  project_id?: string;
  hook_type: string;
  setup_chapter_id?: string | null;
  resolved_chapter_id?: string | null;
  status: string;
  importance: string;
  description: string;
};

export type Foreshadowing = {
  id: string;
  project_id?: string;
  setup_chapter_id?: string | null;
  expected_payoff_chapter_id?: string | null;
  actual_payoff_chapter_id?: string | null;
  status: string;
  description: string;
  clue_text: string | null;
};

export type MemoryItem = {
  id: string;
  layer: string;
  epistemic_status: string;
  memory_type: string;
  importance: string;
  content: string;
  chapter_number: number | null;
  location: string | null;
  extra_metadata?: {
    kind?: string;
    scene_handoffs?: Array<{
      scene_number?: number;
      what_happened?: string;
      character_changes?: string[];
      new_information?: string[];
      open_questions?: string[];
      next_scene_requirements?: string[];
      who_knows?: Record<string, string[]>;
      unknown_to?: Record<string, string[]>;
    }>;
    memory_validation?: {
      overall?: string;
      findings?: Array<{ severity?: string; category?: string; problem?: string }>;
    };
  };
};

export type ContextPackPreview = {
  chapter_number: number;
  chapter_title: string;
  story_arc: {
    title: string;
    start_chapter_number: number;
    end_chapter_number: number;
    summary: string;
  } | null;
  next_plot_beat: string;
  context: {
    open_hooks: string[];
    forbidden_knowledge: Record<string, string[]>;
    current_arc: string;
    memory_brief: string;
    memories: Array<{ content: string; memory_type: string; importance: string }>;
  };
  memory_package: {
    token_estimate: number;
    dropped_for_budget: number;
    unresolved_hooks: string[];
    foreshadowing: string[];
    recent_chapters: Array<{
      chapter_number: number;
      title: string;
      summary: string;
      scene_handoffs?: Array<{ what_happened?: string; open_questions?: string[] }>;
    }>;
    semantic_hits: Array<{ content: string; chapter_number: number | null }>;
  };
  visible_text: string;
};

export type TimelineItem = {
  id: string;
  sequence: number;
  in_world_time: string | null;
  title: string;
  description: string | null;
  location: string | null;
};

export type LlmSettings = {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url: string | null;
  temperature: number;
  max_tokens: number | null;
  api_key_env_name: string | null;
};

export type ResearchStage = {
  id: string;
  title: string;
  detail: string;
  status: "done" | "running" | "pending";
  output: string;
  updated_at?: string;
};

export type ResearchSource = {
  id: string;
  title: string;
  author?: string | null;
  source_type: string;
  path?: string | null;
  url?: string | null;
  chapter_count: number;
  word_count: number;
  selected_dimensions: string[];
  status: string;
};

export type ResearchSession = {
  session_id: string;
  status: "idle" | "running" | "completed" | "failed";
  progress: number;
  stages: ResearchStage[];
  sources: ResearchSource[];
  artifacts: { id?: string; title: string; type?: string; status?: string; content?: unknown }[];
  injection_approved_by?: string | null;
  injection_note?: string | null;
  creative_profile?: Record<string, unknown> | null;
  active_task?: {
    stage?: string;
    status?: string;
    source_title?: string;
    sampled_chapter_numbers?: number[];
    sampled_chapter_titles?: string[];
    message?: string;
  } | null;
};

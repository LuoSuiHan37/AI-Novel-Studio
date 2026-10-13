# Novel creative system

每本小说必须拥有独立的创作上下文。平台规则可以共享，题材、世界、人物、关系、环境和文学风格不能跨项目共享。

## Book-level creative profile

`project.extra_metadata.creative_profile` 是兼容现有项目的书级创作档案，经过 `compile_creative_profile` 规范化后包含：

- `novel_constitution`：核心问题、读者承诺、结局方向、主题、硬约束、禁止处理方式和反复意象。
- `environment_bible`：地理、时间气候、感官素材、社会压力、日常生活、主要地点、环境限制和反复意象。
- `character_dynamics`：人物当前欲望、误解、知识、底线和变化代价。
- `relationship_rules`：关系中的权力差、债务、秘密、误读和变化证据。
- `literary_review_rubric`：人物欲望、场景变化、情绪呈现、环境压力和因果悬念的审稿标准。

旧版研究结果中的 `positioning`、`pacing_controls`、`opening_requirements`、`avoid` 等字段仍会被编译到新档案，不要求已有存档立即迁移。

## Platform separation

中文项目在没有显式指定平台时，会根据 `language=zh` 或 `language=zh-CN` 自动使用 `fanqie` preset。英文项目仍使用现有 AlphaNovel preset。显式 `target_platform` 优先级更高。

番茄 preset 负责语言、段落、章节范围、连载节奏、环境写作和文学质量要求；番茄内容安全须知仍作为所有 Agent 的全局安全边界。

## Chapter contract

章节计划不只描述目标、冲突和钩子，还要求每个场景明确：

- 视角人物想要什么；
- 环境施加了什么压力；
- 人物做出了什么选择；
- 选择付出了什么代价；
- 哪个变化已经不可逆。

正文 Agent 必须把环境写成行动压力，而不是可替换背景；Editor Agent 需要检查环境是否参与冲突、人物选择是否有代价，以及结尾是否由本章因果产生。

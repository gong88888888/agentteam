# Local Skills

优先使用 `RAG-Agent-Toolkit/agent-toolkit/skills` 中已有的本地技能，不额外从 GitHub 拉取。技能是提示词参考文档，不是可执行插件；Agent 在使用前应读取对应 `SKILL.md`。

## 注册表

| 技能 | 适用 Agent | 用途 |
|---|---|---|
| `frontend-design` | ui, frontend | 视觉方向、排版、配色、避免模板化设计 |
| `ui-ux-pro-max` | ui | 67 风格 / 96 配色 / 57 字体 / 13 技术栈的 UI/UX 知识库 |
| `adaptive-frontend-optimization` | frontend, qa | 前端工作流、响应式、异步状态、可访问性优化 |
| `postmortem-to-tests` | qa, retro, review | 事故复盘 → 结构化根因 + 回归测试 |

注册表：`skills/registry.yaml`；`specs/agent-specs.yaml` 中相关角色已声明 `skills` 字段。

## 使用

```bash
python -m orchestrator.cli skills
python -m orchestrator.cli skills --role ui
python -m orchestrator.cli agent --role ui --input brief.txt --offline
```

`orchestrator.skills.SkillRegistry.prompt_context(role)` 会把技能名、描述、路径注入 Agent 系统提示；不会把整份技能文档塞进上下文，Agent 需要时自行读取 `SKILL.md`。

## 校验

```bash
python -I specs/validate_specs.py
```

校验器会检查：
- 12 份 Agent 规格引用的技能都已注册；
- 技能文件存在、frontmatter name 一致；
- 注册表无缺失路径。

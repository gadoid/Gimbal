# Director 重构 — 对话交接文档

> 用途:把当前会话的关键上下文、已确定的设计、文件结构、待办打包记录,方便下一次对话从任意点继续。
> 更新时机:每个阶段讨论结束、跨阶段决策落地、目录结构变化时,**主动同步本文件**。

---

## 0. 项目目标

对 `d:\Gimbal\Gimbal\.claude\skills\director\` skill 做**讨论式重构**——不动代码,先把 5 个阶段的 I/O 契约、judgment 边界、edge cases 逐项敲定,再决定实施。整体结构(5 阶段流水线 + `script.json` 中间产物 + 静态/动态二义规则)被评估为"基本合理",重构主要解决边缘问题与文档明确化,**不砍掉**核心抽象。

---

## 1. 已创建的项目结构

```
d:\Gimbal\Gimbal\director-refactor\
├── fixtures\        # 回归样本(留空)
├── notes\
│   ├── DECISIONS.md # 决策日志(D-NN-XX 编号,每阶段一节,状态 4 种)
│   └── HANDOFF.md   # 本文件:对话交接
└── stages\
    ├── 01-analyze-flow.md        # analyze_flow.py
    ├── 02-script.md             # script_init.py + model 编辑
    ├── 03-gap-resolution.md     # 模型 + script_lint.py
    ├── 04-assemble.md           # script_assemble.py
    └── 05-screening.md          # validate_scenario.py + 模型审查
```

每个 stage 文件按统一模板写:

```
## Input
## Output
## Mechanical vs Judgment
## Boundaries / Edge Cases
## Open Questions        ← 待填
```

所有"Open Questions"初始为空,讨论中提出的问题登记在这里,达成共识后搬到 `DECISIONS.md`。

---

## 2. 当前进度

| 阶段 | 状态 |
|---|---|
| 0. 项目骨架 + 5 阶段文件 | ✅ 完成 |
| 1. Stage 1 analyze_flow 讨论 | 🟡 准备开始 |
| 2. Stage 2 script 讨论 | ⬜ |
| 3. Stage 3 gap-resolution 讨论 | ⬜ |
| 4. Stage 4 assemble 讨论 | ⬜ |
| 5. Stage 5 screening 讨论 | ⬜ |
| 6. 整理为最终重构方案 | ⬜ |

**下一步**:进入 Stage 1 讨论。

---

## 3. 5 阶段流水线总图

```
capture.ndjson ─┐
                │
golden e2e.json ┼─► [1] analyze_flow.py
                │     out: flow.json + flow.md            [mechanical]
                ▼
              flow.json ──► [2a] script_init.py
                              out: script.json skeleton    [mechanical]
                            [2b] model edits                [JUDGMENT]
                ▼
              script.json ──► [3]  gap-resolution (model)
                                  + script_lint.py          [mechanical]
                ▼
              script.json ──► [4] script_assemble.py
                              out: scenario.json            [mechanical]
                ▼
              scenario.json ─► [5a] validate_scenario.py    [mechanical]
                               [5b] model review            [JUDGMENT]
                ▼
              final scenario (schema-valid, replayable)
```

判断点位置(模型必须介入):
- **[2b]** scripting: 哪些 KEEP/DROP/collapse、decision_reason
- **[3]** gap-resolution: 每个 missing_producer 选 static / lookup / open
- **[5b]** final review: 业务故事是否连贯

其它阶段为纯机械。

---

## 4. 已识别的核心设计原则(从原 SKILL 提炼,**不要破坏**)

1. **script.json 是审计中间产物**: 把每个模型判断落到数据字段,后续步骤不再判断。
2. **静态 vs 动态二义规则**(三层防御):
   - `analyze_flow.static_constant_candidate` 启发式标记
   - SKILL/schema 文档化
   - `validate_scenario.py` 硬性 lint
3. **`script_lint` 与 `validate_scenario --script` 互锁**: 防 `script_assemble` 静默丢步。
4. **完整审计**: dropped/collapsed 步骤保留在 script.json。
5. **JSONPath 不发明**: 脚本只产出"对真实 response 验证过的"路径。
6. **id 解析源可插拔**: 本地 catalog → 未来 Plate/EndpointSpec MCP。

---

## 5. 已识别的边缘问题(初版,讨论中可补充/缩减)

### Stage 1
- `summary` 字段够不够?要不要加 `coverage_vs_golden`、`id_kinds` 等聚合?
- id 跨 response 复用时取最早一次,可能漏选非权威响应
- short-numeric id 失明(SNOWFLAKE `^\d{12,}$`)
- scalar graph 看不见 list data(已有 `bulk_extract_candidates` advisory,合理)

### Stage 2
- `decision_reason` 自由文本,无法聚类(讨论过可加 `[code] free_text` 前缀)

### Stage 3
- synthetic lookup step 的 `request_body`/`headers`/`path`/`method` schema 未强制化

### Stage 4
- synthetic lookup step 走 step 自带字段,**字段形状未规范化**
- `service` 字段用 `next(iter(services))`,跨 service capture 会错标
- 同 path 多次出现时,`assign.var` 重复注入目标未 dedup-by-var
- `bulk_extract_candidates` 与 single-write rule 张力,缺 `recommended_scope` 提示

### Stage 5
- `--capture` 验证用 path+occurrence 而非 idx,误匹配风险
- `DEFAULT_PROCESS_IDS` 硬编码,扩展靠 `--process-ids`
- synthetic step 的 `order` 与真实 idx 排序时可能歧义

### 跨阶段
- id-resolution source 接口未抽象(目前是 catalog 直读)
- 跨 service capture 假设未显式声明

---

## 6. 讨论工作流约定

每次进入或恢复某一阶段讨论时:

1. 打开 `director-refactor/stages/NN-*.md`,确认当前 "Open Questions" 内容
2. 用户或模型提出问题/决定 → 先在 Open Questions 中更新
3. 达成共识 → 在 `notes/DECISIONS.md` 追加一条 `D-NN-XX`,状态 `ACCEPTED`
4. 否决 → `REJECTED`,留痕备查
5. 暂缓 → `DEFERRED`
6. 阶段讨论结束 → 在本 HANDOFF 的"当前进度"表更新状态

---

## 7. 关联文件快速链接

- 原 skill: [d:\Gimbal\Gimbal\.claude\skills\director\SKILL.md](../.claude/skills/director/SKILL.md)
- 原 references: [d:\Gimbal\Gimbal\.claude\skills\director\references\](../.claude/skills/director/references/)
- 原 scripts: [d:\Gimbal\Gimbal\.claude\skills\director\scripts\](../.claude/skills/director/scripts/)
- 决策日志: [DECISIONS.md](./DECISIONS.md)
- 阶段文件: [stages/](../stages/)

---

## 8. 下一次对话开场建议

下次进入时可直接说:

> "继续 Stage 1 讨论,从 `stages/01-analyze-flow.md` 的 Open Questions 开始。"

或:

> "跳到 Stage 3,我们先聊 gap-resolution。"

我会先 `Read` 对应文件 + 本 HANDOFF 的"当前进度"段,确认上下文,再继续。

---

## 9. 元信息

- 创建时间: 当前会话
- 当前阶段: 0 完成,准备进入 1
- 待办: 等待用户启动 Stage 1 讨论
- 最近一次更新: 本文件初版
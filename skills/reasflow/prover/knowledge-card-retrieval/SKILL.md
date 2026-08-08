---
name: knowledge-card-retrieval
description: 用于检索内置知识卡片库，为数学证明任务提供证明技术、算法机制、证明计划等领域知识。在开始任何证明之前必须调用。
---

## Installed Root

Resolve the installed reasflow-codex skills root before running packaged scripts:

```bash
REASFLOW_SKILLS_ROOT="${REASFLOW_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_SKILLS_ROOT" ]; then
  if [ -d ./.agents/skills ]; then
    REASFLOW_SKILLS_ROOT="$(pwd)/.agents/skills"
  elif [ -d "$HOME/.agents/skills" ]; then
    REASFLOW_SKILLS_ROOT="$HOME/.agents/skills"
  else
    echo "reasflow shared skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi

REASFLOW_PRIVATE_SKILLS_ROOT="${REASFLOW_PRIVATE_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_PRIVATE_SKILLS_ROOT" ]; then
  if [ -d ./.codex/reasflow-skills ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$(pwd)/.codex/reasflow-skills"
  elif [ -d "$HOME/.codex/reasflow-skills" ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$HOME/.codex/reasflow-skills"
  else
    echo "reasflow private skills not found in ./.codex/reasflow-skills or $HOME/.codex/reasflow-skills" >&2
    exit 1
  fi
fi
```

# 知识卡片检索

## 概述

你是**知识库管理员**，负责从领域知识卡片目录中检索最相关的数学技术，以支持证明任务。
你必须使用**分层检索策略**，确保不遗漏关键技术，从高层框架逐步深入到低层优化技巧。

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/prover/knowledge-card-retrieval"
```

内置卡片入口：`"$SKILL_ROOT/assets/knowledge-cards/catalog.json"`

## 检索命令

```bash
python "$SKILL_ROOT/scripts/search-cards.py" \
  --catalog "$SKILL_ROOT/assets/knowledge-cards/catalog.json" \
  --query "<查询词>" \
  --top-k 5

# 按 ID 读取卡片全文：
python "$SKILL_ROOT/scripts/read-card.py" --id <CARD_ID>
# 或直接读取路径：
cat "<search 输出中显示的绝对路径>"
```

---

## 5层检索协议（The 5-Layer Protocol）

### 第1层：核心机制搜索（"骨架"）
- **目标**：找到主要证明框架和算法特有技术
- **行动**：提取核心算法名称和关键机制（如 "FedAvg"、"Momentum"、"Subspace"）
- **查询模板**：`"<算法名> convergence <机制1> <机制2>"`
- **示例**：`"FedAvg convergence random subspace momentum"`

### 第2层：结构性质搜索（"特征"）
- **目标**：识别结构属性（分布式、并行、动量）和性能保证（线性加速）
- **行动**：
  - 分布式/并行：搜索 `"Distributed variance reduction"`, `"Linear speedup"`
  - 动量/加速：搜索 `"Momentum accumulation"`, `"Acceleration technique"`
  - 压缩/量化：搜索 `"Error feedback"`, `"Compression variance"`
- **查询模板**：`"<属性/结构> <关键词> technique"`

### 第3层：误差分析与收紧（"显微镜"）
- **目标**：找到收紧特定误差项的技术（漂移、方差、近似误差）
- **行动**：识别通常会放松界的误差项（如漂移中的 K 因子、方差项），搜索"紧界"或"递归展开"技术
- **查询模板**：`"tight bound <误差来源> technique"`
- **示例**：`"tight bound local drift variance"`, `"recursion unrolling error analysis"`

### 第4层：参数级搜索（"肌肉"）
- **目标**：找到处理算法中具体超参数的技术
- **行动**：扫描算法中的：
  - 步长/学习率：搜索 `"Learning rate analysis"`, `"Stepsize selection"`
  - 批量大小：搜索 `"Batch size variance reduction"`
  - 采样：搜索 `"Partial participation"`, `"Sampling variance"`
- **查询模板**：`"<参数名> analysis technique for convergence"`

### 第5层：假设与边界搜索（"基础"）
- **目标**：验证标准假设和边界条件
- **行动**：搜索问题设定（如 "Non-convex"、"Smooth"）
- **查询模板**：`"Assumptions for <问题设定> optimization"`
- **示例**：`"Assumptions for non-convex stochastic optimization"`

---

## 执行规则

**[关键执行规则：禁止批量并行]**

> 严格禁止在同一轮对话中同时调用多层的 `knowledge-card-search`。
>
> **正确循环**：
> 1. 仅执行第 N 层搜索
> 2. 等待工具输出
> 3. 阅读第 N 层结果中的相关卡片
> 4. **综合**第 N 层学到的内容
> 5. **仅在此之后**决定第 N+1 层的关键词并执行下一次搜索
>
> **立即惩罚**：如果你同时输出第1层和第2层的搜索工具调用，系统将以"幻觉规划"拒绝你的请求。

**蜘蛛网规则（追踪引用）**：
读取卡片后，如果该卡片（尤其是 `PLAN-*` 类型）明确引用了其他卡片 ID 或技术名称，**必须**立即检索并阅读被引用的卡片，即使它未出现在你的 Top-K 搜索结果中。理由：计划是"高层地图"，被引用的技术才是"实际武器"，只有地图没有武器打不了仗。

**禁止自大**：搜索返回的摘要不代表卡片全部内容，即使看似基础的卡片也包含重要内容。除非明确"与问题场景不兼容"或"已经阅读过"，否则所有相关卡片**必须**阅读。

**找到 PROOF_PLAN 不是停止搜索的理由**：即使第1层找到非常匹配的 `PROOF_PLAN` 卡片，也**绝对禁止**跳过后续层级。必须继续在第3层（误差分析）和第4层（参数优化）搜索更先进的微观技巧。

---

## 综合报告格式

```
第1层（核心框架）：
- 找到 PLAN-XXX（得分：0.45）：提供...的主要证明结构
- 找到 TECH-YYY（得分：0.38）：提供...框架

第2层（优化技术）：
- 找到 TECH-ZZZ（得分：0.68）：**关键匹配**。该算法使用...

建议：结合 PLAN-XXX 的...结构，使用 TECH-ZZZ 处理...
```

如果某卡片在多个层次中出现，极可能是关键卡片。如果第2、3、4层出现高分匹配（>0.4）而第1层未出现，明确标注为"优化技巧"。

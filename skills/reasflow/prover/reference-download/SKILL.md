---
name: reference-download
description: 下载和处理 arXiv 学术文献，提取 LaTeX 源码中的算法、引理、定理等数学内容，为证明任务提供参考资料。
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

# 文献下载与处理

## 概述

本 skill 提供下载、解压和分析学术文献（尤其是 arXiv LaTeX 格式论文）的完整工作流，支持数学证明项目高效获取参考资料。

## 快速开始

### 下载 arXiv 论文

```bash
python "$REASFLOW_PRIVATE_SKILLS_ROOT/prover/reference-download/scripts/download-arxiv-reference.py" \
  --arxiv-id <arXiv_ID> \
  --output-dir prover/references/<ref_name> \
  --workspace <workspace>

# 示例：
# --arxiv-id 2101.11203 --output-dir prover/references/ref_fedavg
```

下载完成后，脚本会列出所有 `.tex` 文件。

### 搜索数学内容

下载后，使用 `rg` 高效定位数学内容：

```bash
# 定位所有引理和定理位置（推荐优先执行）
rg "\begin\{lemma\}|\begin\{theorem\}|\begin\{assumption\}" prover/references/<ref_name>/ -n

# 定位算法
rg "\begin\{algorithm\}|\begin\{algorithmic\}" prover/references/<ref_name>/ -n

# 定位证明
rg "\begin\{proof\}" prover/references/<ref_name>/ -n
```

---

## 工作流程

### 第1步：下载与解压

- 使用下载脚本自动完成下载和解压
- 文件自动组织到 `<workspace>/prover/references/` 下
- 支持 `.tar.gz` 和 `.zip` 格式

### 第2步：搜索与定位数学内容

**必须使用 `rg` 先锁定，不要直接读取长文件**：

```bash
# 全面概览（推荐首先执行）
rg "\begin\{lemma\}|\begin\{theorem\}|\begin\{assumption\}|\begin\{algorithm\}" \
  prover/references/<ref_name>/ -n

# 搜索收敛性相关内容
rg "convergence\|converge\|descent" prover/references/<ref_name>/ -l
```

**必须深入阅读的内容**：
- ✅ 所有 Assumption 环境 — 了解假设条件
- ✅ 所有 Algorithm 环境 — 理解计算框架
- ✅ 关键 Lemma 和 Theorem — 理解中间结果和主要结论
- ✅ 核心证明段落 — 学习证明技巧和框架

**大段落阅读策略**：
- 当 `rg` 定位到有价值的内容跨越多行（如第 600–1600 行），直接读取整个区间
- 耐心读完完整数学论证，不要跳过或概括
- 使用足够大的 `limit` 减少分片读取次数

### 第3步：文献整合

- 向子智能体提供精确的文件引用（具体路径 + 行号范围）
- 记录发现的证明技巧和框架
- 说明文献价值在于**思路借鉴**和**框架复用**，不仅仅是结论引用

---

## 文件组织结构

```
<workspace>/prover/references/
├── ref_paper1/
│   ├── main.tex
│   ├── sections/proof.tex
│   └── figures/
└── ref_paper2/
    └── ...
```

---

## 完整性核查清单

阅读文献后，自我核查：

- ✅ 所有 Assumption 已仔细阅读并理解
- ✅ 所有 Algorithm 已完整分析
- ✅ 所有关键 Theorem 和 Lemma 已充分理解
- ✅ 重要证明段落已仔细研究
- ✅ 已识别证明技巧和数学框架
- ✅ 没有遗漏任何重要章节或附录文件（用 `find` 确认所有 `.tex`）

---

## 注意事项

- **严禁偷懒**：必须充分理解下载文献的内容，不能只是粗略浏览
- **确保完整性**：使用 `rg` 或 `find` 查找所有 `.tex` 文件，不要遗漏重要章节或附录
- **多文件处理**：如果参考文献有多个 `.tex` 文件，**全部**都要审阅后再提供给子智能体

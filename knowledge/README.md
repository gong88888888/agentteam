# Knowledge Base (RAGFlow-inspired, local)

本地混合检索知识库。**不直接运行 RAGFlow**（它依赖 Elasticsearch/MySQL/Redis 等重型组件，不适合单机一人公司场景），而是复用其核心检索思想：解析 → 切块 → 向量化 → 混合检索 → 重排 → 引用。

## 架构

```
docs / specs / rubrics / skills / prompts
        │
        ▼
Markdown-aware chunker          # 标题、段落、代码块；CJK 友好 token
        │
        ├── SQLite FTS5           # 词法 BM25
        └── bge-m3 (Ollama)       # 1024 维向量；不可用时 hash:256 回退
        │
        ▼
RRF 融合 + 独立 rerank            # dense + 查询词覆盖 + 标题/短语 + 去冗余
        │
        ▼
citation: path#heading
```

## 与 RAGFlow 的对应关系

| RAGFlow 能力 | 本实现 |
|---|---|
| 文档解析 | `orchestrator/knowledge/chunker.py`：Markdown 标题/段落切块 |
| Chunking | 按 H1-H4 分节；长节按段落切分，保留 heading |
| Embedding | `bge-m3:latest` via Ollama `/api/embed`；离线回退 `hash:256` |
| 混合检索 | SQLite FTS5 BM25 + 向量 cosine，RRF 融合 |
| Rerank | `orchestrator/knowledge/rerank.py`：RRF + dense + 查询词覆盖 + 标题命中 + 去冗余；保留 base_score |
| Citation | `path#heading`，返回 `chunk_id`、`source_type`、`score` |
| Metadata filter | `source_type`、`path_prefix` |
| 增量索引 | 文件内容哈希 + 每文档 embedding 模型检查 |
| 知识库隔离 | `source_type`：design/spec/rubric/skill/eval/prompt/knowledge |

## 命令

```bash
# 索引项目文档（默认 bge-m3；不可用则 hash）
python -m orchestrator.cli kb-index
python -m orchestrator.cli kb-index --backend hash
python -m orchestrator.cli kb-index --backend ollama

python -m orchestrator.cli kb-stats
python -m orchestrator.cli kb-query "共享文件冲突 租约" --top-k 5
python -m orchestrator.cli kb-query "前端 可访问性" --source-type skill --top-k 5
python -m orchestrator.cli kb-query "回滚 演练" --json
```

## 评测

`eval/kb_eval.py` 使用临时库 + hash embedding，不依赖网络；22 个用例同时跑 rerank 与 RRF baseline，报告 recall@5、MRR、rerank gain 与 source filter：

```bash
python eval/kb_eval.py
```

真实库（`data/knowledge.db`，bge-m3）可用 `--real` 复测。

## 注意

- 中文 FTS 用字符 unigram + bigram 写入 `chunks_fts.tokens`，避免 unicode61 对中文分词不佳。
- 向量检索当前是全量 cosine（本地小库足够）；超过数万 chunk 再引入 sqlite-vec 或独立向量库。
- `data/knowledge.db` 已被 `.gitignore` 忽略；索引可重建。

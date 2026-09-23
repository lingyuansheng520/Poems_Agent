# 巴蜀杜诗智能体项目 · 技术实施手册

> 项目：人工智能赋能巴蜀杜诗学数据库建设与智能体应用研究
> 仓库：`lingyuansheng520/Poems_Agent`（私有）　工程目录：`D:/pycharm文件/杜诗`
> 时间盒：**8 周**，第 4 周末产出可对外演示版本
> 配套文档：[`docs/git-workflow.md`](./git-workflow.md)（协作与提交规范）

---

## 0. 现状一句话

技术侧已完成约 35%（检索链路闭环），数据与知识侧约 5%（注释 0.9%、意象 0.9%、溯源字段近乎全空）。
**短板不在模型，在数据。因此整个计划的重心是：先把工程做成"数据一填就变聪明"的容器。**

| 已有 | 缺失 |
|---|---|
| LangGraph 编排（rewrite → retriever → generate） | `main.py` 空，无 API、无界面 |
| BM25(jieba) + Chroma 融合（0.4 / 0.6） | 无 MySQL，文件即真相 |
| 本地 bge-base-zh + bge-reranker | 诗歌 ID 只填了 2 条，无法按主键定位 |
| CSV 740 首 / 18 字段，694 条可入库 | 实体类字段不进检索正文，问不出来 |
| 文学组《数据收集与标注规范》已定稿 | 无评测集、无基线数字 |

---

## 1. 三条不可妥协的原则

1. **单一真相源 = MySQL**。CSV 降级为"文学组交过来的交换格式"，单向导入，业务层禁止直接读 CSV。
2. **检索层只回 `poem_id`**。正文、注释、出处一律回 MySQL 取；Chroma 内不存第二份正文。
3. **证据链靠数据模型承载**，不靠 prompt。每条知识必须携带 `source_doc_id` + `locator` + `status`，UI 据此展示"查得到 / 未收集 / 待考证"。

缺失值统一使用受控词：`未收集` / `待考证` / `已核对无相关记录` / `已核实` / `有争议`。
禁止出现空白、"无"、"N/A"、"暂时未录入" 等多种口径并存（当前代码中 `暂时未录入` 与未生效的 `'未著录'` 过滤即属此类，必须在阶段一消除）。

---

## 2. 目录结构（已按实际代码对齐）

**当前实际结构**（2026-09-23 已完成搬迁，`git status` 显示为 rename）：

```
backend/
  main.py                      空 → 阶段三写入 FastAPI 入口
  Config/
    __init__.py
    config.py                  Settings + 资源根 DATA_ROOT
  Schema/
    schema.py                  RewriteResult（后续迁出为 schemas/）
  Agent/                       智能体域：编排 + 检索 + 模型
    agent.py                   LangGraph 图（model_call / search_router）
    model/LLM.py               llm 与 rewrite_llm
    langgraph_state/State.py   messages / search_content / citations …
    RAG/
      load_document.py         CSV → Document
      BM25Retriever.py         BM25 + jieba
      vector_retriever.py      Chroma 检索器封装
      define_rag.py            embedding 与向量库初始化
      Rerank.py                bge-reranker 压缩
      RRF.py                   BM25 + 向量融合（0.4 / 0.6）
      recall_search.py         rewrite_query / retriever
      knowledge/杜诗.csv       语料（交换格式）
      embedding_models/        本地模型，不入库
      vector_db/               Chroma 持久化，不入库
```

**目标结构**（在现有基础上增量，不推翻 `Agent/` 聚合方式）：

```
backend/
  Agent/                       保持现有结构，内部新增：
    RAG/contract.py            字段契约（或按 3.2 放在 Config/ 下）
  Config/  contract.py  字段契约唯一出处（推荐位置）
  schemas/     chat.py  poem.py  entity.py  evidence.py
  api/
    deps.py
    v1/  chat.py  poems.py  entities.py  admin.py  stats.py  feedback.py
  services/    chat_service.py  retrieval_service.py  ingest_service.py  eval_service.py
  db/          base.py  session.py  models/  crud/  alembic/
  scripts/     assign_ids.py  import_csv.py  build_index.py  download_models.py
docs/          git-workflow.md  implementation-plan.md
```

> **不必照搬任何"标准"目录名**。`Agent/` 把编排、检索、模型聚在一个域里是合理的，
> 后续新增的 `api/`、`db/`、`schemas/`、`services/` 与它平级即可。
> 真正要守的只有：路径集中管理、契约唯一出处、单一真相源。

技术选型：SQLAlchemy 2.0 + Alembic + PyMySQL + Pydantic v2。
**暂不上全套 async**：本地 1.5GB 模型，用同步 `def` 路由 + `uvicorn --workers 1`，流式走 SSE。

---

## 3. 阶段一 · 地基（本周）

### 3.1 统一资源根 `DATA_ROOT`（先做这一步，30 分钟）

搬迁后所有资源都集中在 `backend/Agent/RAG/` 下，但代码里仍有几处按旧路径拼接。
**做法：只在 `Config/config.py` 里定义一次，其余模块一律引用它。**

```python
# backend/Config/config.py
_backend_root = Path(__file__).resolve().parent.parent      # backend/
DATA_ROOT     = _backend_root / 'Agent' / 'RAG'             # 资源根：唯一出口

# Settings 中：
knowledge_path: str = str(DATA_ROOT / 'knowledge' / '杜诗.csv')
```

需要改为引用 `DATA_ROOT` 的位置（搬迁后遗留的失效点）：

| 文件 | 现写法 | 改为 |
|---|---|---|
| `Agent/RAG/load_document.py` | `_base_dir/'RAG'/'knowledge'/杜诗.csv` | `DATA_ROOT/'knowledge'/杜诗.csv` |
| `Agent/RAG/define_rag.py` | `_base_dir/'vector_db'` | `DATA_ROOT/'vector_db'` |
| `Agent/RAG/define_rag.py` | `_base_dir/'Agent'/'RAG'/'embedding_models'/…` | `DATA_ROOT/'embedding_models'/…` |
| `Agent/RAG/Rerank.py` | `_base_dir/'Agent'/'RAG'/'embedding_models'/…` | `DATA_ROOT/'embedding_models'/…` |

> 这次三个点同时失效，正是因为路径散落在四个文件里。以后再挪目录，**只需要改这一行**。

冒烟测试（只走 BM25，不加载 1.5GB 模型，秒级出结果）：

```bash
python -c "from backend.Agent.RAG.BM25Retriever import get_bm25_retriever as g; print(g().invoke('锦官城')[0].metadata['title'])"
```

### 3.2 新建契约文件（建议 `backend/Config/contract.py`）

放在 `Config/` 而非某个域目录下，因为它是loader、导入器、API 三方共用的东西。

```python
COLUMNS = ['诗歌ID','诗歌篇名','诗文正文','版本信息','异文记录','原文出处','体裁',
           '创作时间','创作地点','相关人物','相关地点','典故','意象','历史事件',
           '注释','评点','负责人','数据状态']        # 冻结：不得改名、不得插列

UNKNOWN = '未收集'
PLACEHOLDERS = {UNKNOWN,'待考证','已核对无相关记录','已核实','有争议'}

TEXT_FIELDS = ['诗歌篇名','诗文正文','体裁','创作时间','创作地点','相关人物',
               '相关地点','典故','意象','历史事件','注释','评点','异文记录']  # 进 embedding
META_ONLY   = ['版本信息','原文出处','负责人','数据状态']                    # 仅筛/溯源
```

> 关键：意象、相关地点、历史事件、相关人物目前只在 metadata 里，**不参与 embedding**，文学组填满了也问不出来。放进 `TEXT_FIELDS` 后一次性解决。

### 3.3 改造 `backend/Agent/RAG/load_document.py`

- `csv.DictReader` **按列名取值**，禁止按下标；缺列降级为 `UNKNOWN` 并 `logger.warning`，禁止抛 `KeyError`；多出的列进 metadata。
- 空值一律渲染为 `UNKNOWN`；保留现有 `_clean()` 对 U+FFFC / 零宽字符的清理。
- `page_content` 按 `TEXT_FIELDS` 循环拼 `【字段名】值`，占位值跳过。
- metadata 至少含：`poem_id`（缺失时 `BSDS{原始行号:04d}`）、`row`（原始行号）、`edition`、`source`、`status`、`completeness`（非占位字段占比）。

### 3.4 修复 `backend/Agent/RAG/recall_search.py`

- `doc_id` 取 `poem_id`；`citations` 增加 `edition` / `status` / `completeness`。
- `_head()` 过滤改为 `if v and v not in PLACEHOLDERS`（现 `'未著录'` 是失效死条件）。
- `Agent/RAG/Rerank.py` 的 `top_n` 由 3 调为 5。
- **兜底分支**：检索为空或最高分低于阈值 → 直接返回固定话术并跳过 LLM：
  `本演示库未收录相关材料，建议参看《杜诗详注》相关卷次。`

### 3.5 批量补 ID（`scripts/assign_ids.py`）

按当前行序生成 `BSDS0001…BSDS0694`，旧 CSV 另存备份。**不要手填**，也不要在此阶段调整行序（`row` 已作为 metadata 落进索引，行序一动引用就错位）。

### 3.6 索引指纹（`scripts/build_index.py`）

```python
fingerprint = sha256(CSV) + str(row_count) + TEXT_FIELDS_VERSION
persist_dir = DATA_ROOT / 'vector_db' / <fingerprint[:8]>
```
写 `DATA_ROOT/'vector_db'/'version.json'`；`define_rag.init_vector` 改为读指纹而非"目录存在即复用"。

### 阶段一验收（必须全绿）

```bash
python -c "from backend.Agent.RAG.load_document import load_document as l;d=l();print(len(d));print(d[0].metadata.keys())"
python -c "from backend.Agent.RAG.BM25Retriever import get_bm25_retriever as g; print(g().invoke('锦官城')[0].metadata['title'])"
```
- [ ] `len(docs)` 仍为 694
- [ ] metadata 中 `poem_id / edition / source / status / completeness` 均有值
- [ ] 故意删除 CSV 的"意象"列后运行不报错，仅告警
- [ ] 提问命中答案时，右侧引用能指到具体篇目与出处
- [ ] 提问库外内容时得到拒答话术，而非模型编造
- [ ] 修改一行 CSV 后重跑索引，目录变化且触发重建

---

## 4. 阶段二 · MySQL 数据层（W2）

### 4.1 库与字符集

`utf8mb4` / `utf8mb4_unicode_ci`。中文全文检索用 ngram parser：

```sql
ALTER TABLE poem ADD FULLTEXT INDEX ft_body (body) WITH PARSER ngram;
```

### 4.2 表清单

| 表 | 作用 | 关键字段 |
|---|---|---|
| `poem` | 诗歌主表 | `id`(BSDSxxxx PK) `title` `alias` `body` `genre` `time_raw` `time_start/end` `owner` `status` `completeness` |
| `source_doc` | 文献 / 注本 | `id` `title` `author` `edition` `publisher` `year` |
| `citation` | **证据链核心** | `poem_id` `field` `source_doc_id` `locator`(卷次/页码) `quote` `status` |
| `entity` | 统一实体 | `id` `type`(人物/地名/典故/意象/事件) `name` `description` `status` |
| `poem_entity` | 诗—实体关系（带证据） | `poem_id` `entity_id` `line_ref`(对应诗句) `note` `citation_id` `status` |
| `poem_variant` | 异文 | `poem_id` `line_no` `variant_index` `variant_text` `note` |
| `annotation` | 注释 | `poem_id` `target` `content` `citation_id` `annotator` `status` |
| `comment` | 评点 | `poem_id` `commenter` `content` `citation_id` `note_type` `status` |
| `verification_log` | 审核留痕 | `poem_id` `field` `verifier` `from_status` `to_status` `created_at` |
| `qa_log` | 问答日志 | `query` `answer` `citations`(JSON) `latency_ms` `flagged` |
| `eval_case` / `eval_run` | 评测集 / 跑分 | `question` `gold_answer` `gold_source` ｜ `run_id` `hit@5` `evidence_rate` `hallucination_rate` |
| `import_batch` | 导入批次 | `file_sha256` `row_count` `imported_at` `operator` |

索引：`poem(title)`、`poem(genre)`、`entity(name)`、`poem_entity(poem_id, entity_id)`。

> **不要建 18 列宽表**。宽表做不了"锦官城出现在哪些诗里"这类反查，而这正是知识组织创新点的落点。
> **暂不引入 Neo4j**。数据量仅数百诗、数千实体，`poem_entity` 邻接表足够；图可视化导出给 pyvis。需做三跳以上路径查询时再评估图库。

### 4.3 CSV → MySQL 映射（`scripts/import_csv.py`）

| CSV 列 | 落库位置 |
|---|---|
| 诗歌ID / 篇名 / 正文 / 体裁 / 创作时间 | `poem` |
| 版本信息 / 原文出处 | `source_doc` + `citation.locator` |
| 异文记录 | `poem_variant` |
| 相关人物 / 相关地点 / 典故 / 意象 / 历史事件 | `entity` + `poem_entity`（带 `line_ref`） |
| 注释 / 评点 | `annotation` / `comment` |
| 负责人 / 数据状态 | 各表 `owner` / `status`（必须是受控词） |

导入器要求：`--dry-run` 先出 diff 报告（新增/修改/删除的行与字段）；落库时按 `poem.id` upsert；每批写入 `import_batch`；非法受控词、重复 ID、缺 ID 一律拒绝导入并给出错误行号。

### 阶段二验收

- [ ] CSV 全量导入后，`poem` 行数 = 694，ID 唯一且非空
- [ ] 同一 CSV 导入两次，第二次全部 upsert 无重复
- [ ] 故意写一行非法受控词，导入被拒且报出行号
- [ ] 改一行后重跑，索引重建触发成功

---

## 5. 阶段三 · FastAPI 接口（W3）

| 方法 | 路径 | 用途 | 备注 |
|---|---|---|---|
| POST | `/api/v1/chat/stream` | 流式问答 | SSE：token 流 + 末尾 `citations` 事件 |
| POST | `/api/v1/chat` | 非流式问答 | 供评测脚本与批处理使用 |
| GET | `/api/v1/poems` | 列表 | `q / genre / place / year / status` 过滤 + 分页 |
| GET | `/api/v1/poems/{id}` | 详情 | 正文、异文、注释、实体一次返回 |
| GET | `/api/v1/poems/{id}/evidence` | 证据链 | 证据面板直接消费 |
| GET | `/api/v1/entities` | 实体检索 | `?type=&q=` |
| GET | `/api/v1/entities/{id}/poems` | 实体反查 | 「锦官城」出现在哪些诗 |
| GET | `/api/v1/search` | 检索调试 | 返回 `poem_id + score + 片段`，用于校准阈值 |
| POST | `/api/v1/admin/import-csv` | 导入 | 传 `dry_run=true` 出报告 |
| POST | `/api/v1/admin/reindex` | 重建索引 | 换 persist 目录 + 指纹校验 |
| GET | `/api/v1/stats` | 统计 | 各字段填充率、篇目数、数据量（汇报 PPT 直接取） |
| POST | `/api/v1/feedback` | 反馈 | 标记"回答有误"，写入 `qa_log.flagged`，积累幻觉样本 |
| GET | `/api/v1/health` | 健康检查 | 含模型是否已预热 |

要点：

- `FastAPI(lifespan=...)` 中预热 embedding、reranker、融合检索器（1.5GB 加载需数十秒），否则首个请求必超时。
- 鉴权先用 `X-API-Key`，不做用户系统；开启 CORS 以支撑后续前端/小程序。
- 全部出入参用 `schemas/` 下的 Pydantic 模型，禁止直接返回 ORM 对象。

### 阶段三验收

- [ ] 浏览器可完成一次问答，右侧显示"诗句 → 注释/典故 → 注本出处（含卷次页码）"
- [ ] 字段为空的知识显示为「未收集」而非消失
- [ ] `/stats` 返回的数字可直接截图进汇报材料
- [ ] 重启服务后第一次请求不超时（预热生效）

---

## 6. 阶段四 · 演示与评测（W4）

1. **界面**：先用 Gradio Blocks 直接 `from backend.Agent.agent import graph_app`（不经过 FastAPI），左对话、右证据面板；稳定后再包进 API。**先把能看的那一版拿出来**。
2. **演示态开关**：顶部切换「仅已核实数据 / 含待考证内容」，后者必须在回答中显式提示证据不足。
3. **评测集**：30–50 题，每题含 `question / gold_answer / gold_source`，覆盖典故解释、地名人物关联、异文辨析、诗句出处四类。
4. **指标**：`hit@5`（正确答案是否在前 5 条检索结果）、`evidence_rate`（回答引用是否指向真实条目）、`hallucination_rate`（人工判定或抽样复核）。结果写 `eval_run`。
5. **产出**：《智能体内测报告 V1》——这是第一份阶段性成果材料，也是论文唯一的实验数据来源。

---

## 7. 八周节奏

| 周 | 主线 | 交付 |
|---|---|---|
| W1 | 契约层 + 引用修复 + 锁定演示篇目 | 后台链路可信、可追溯 |
| W2 | MySQL 建模 + 导入器 + 索引重建 | 数据有了单一真相源 |
| W3 | FastAPI + SSE + Gradio 证据面板 | **第一个可演示版本** |
| W4 | 评测集 + 指标 + 内测报告 | 拿到量化数字 |
| W5–W6 | 实体关系表 + pyvis 子图可视化 | 知识组织形态可见 |
| W7–W8 | 汇报材料 / 论文提纲 / 数据扩容流程 | 阶段成果交付 |

并行动作（不占关键路径）：把填写模板与 `validate_csv.py` 交给文学组，按 `负责人` 列分工，锁 50 首优先回填。

---

## 8. 明确不做（两个月内）

知识图谱全套产品化、多租户与复杂权限、模型微调（本地 72B / SFT）、Docker 化部署、小程序、多 Agent 协同校勘。
每一项都能吃掉两周，而对演示当天的贡献为零。叙事与实物的落差通过"阶段性说明"处理，不要用透支工期去填。

---

## 附录 A · 高频命令

```bash
# 提交前体检：不得有大文件
python -c "import subprocess,os;fs=subprocess.check_output(['git','ls-files','-z']).decode().split(chr(0));big=[(round(os.path.getsize(f)/1048576,1),f) for f in fs if f and os.path.exists(f) and os.path.getsize(f)>5*1048576];print(big if big else 'OK')"
# 提交前体检：不得有密钥
git ls-files | grep -i -E "\.env$|key|token|secret"
# 建表迁移
alembic revision --autogenerate -m "init schema" && alembic upgrade head
# 服务启动（单 worker）
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

## 附录 B · 缺失值受控词

| 取值 | 含义 |
|---|---|
| 未收集 | 尚未处理，不等于不存在 |
| 待考证 | 有线索但证据不足或相互矛盾 |
| 已核对无相关记录 | 指定范围内完成核对且无发现 |
| 已核实 | 已对照来源核查并保留依据 |
| 有争议 | 保留不同说法，不强制唯一结论 |

`待考证` 与 `有争议` 在智能体回答中必须显式标注为不确定，不得作为确定结论输出。

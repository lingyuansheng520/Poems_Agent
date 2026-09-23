# 协作与版本管理规范

本仓库为「人工智能赋能巴蜀杜诗学数据库建设与智能体应用研究」课题的工程仓库，**私有**。
任何人均不得将 `backend/.env`、模型文件、语料原始数据外传。

---

## 1. 分支约定

| 分支类型 | 命名示例 | 用途 |
|---|---|---|
| `main` | — | 受保护分支，禁止直接 push，只能通过 Pull Request 合入 |
| 功能开发 | `feat/evidence-panel` | 新增能力 |
| 缺陷修复 | `fix/citation-null` | 修 bug |
| 数据更新 | `data/2026-09-23-annotation` | CSV 语料回填、字段修正 |
| 文档 | `docs/git-workflow` | 文档、模板、规范 |

一个改动一个分支，合完即删。

## 2. 日常流程（改代码）

```bash
git checkout main
git pull --rebase origin main
git checkout -b feat/xxx            # 按上表命名
# ……改动……
git add -A
git commit -m "fix: 简述改了什么"
git push -u origin feat/xxx
gh pr create --fill                 # 自动填充标题与正文
gh pr merge --squash                # 合并后可 git checkout main && git pull
```

## 3. 数据更新流程（改 CSV）

CSV 体积约 300KB，入库无压力，**每次导入都必须留下可追溯的提交信息**：

```bash
git checkout -b data/2026-09-23-annotation
python scripts/validate_csv.py      # 先自检，通过才提交（脚本到位后启用）
git add backend/RAG/knowledge/杜诗.csv
git commit -m "data: 文学组回填 XX 首注释与典故（待审核）"
git push -u origin data/2026-09-23-annotation
gh pr create --fill
```

提交信息里写清：**哪一批、谁提供、是否已核实**。这条历史就是论文与中期材料的数据来源记录。

### 冲突预防

- 按 CSV 中的 `负责人` 列分工，**每人只改自己负责的篇目行**；
- 重名篇目一律以 `诗歌ID` 定位，不得以篇名定位；
- 文学组在 GitHub 网页编辑时会自动生成分支与 PR，由工程负责人审阅后合并。

## 4. 字段契约（改动前必读）

- 表头列名与顺序以 `backend/RAG/field_contract.py`（待补充）为准：**不得改名、不得插列**，新增字段只能追加到末尾；
- 缺失值必须使用受控词：`未收集` / `待考证` / `已核对无相关记录` / `已核实` / `有争议`；
- 禁止出现空白单元格、"无"、"N/A"、"暂时未录入" 等多种口径并存；
- `待考证`、`有争议` 的内容在智能体回答中必须显式标注为不确定，不得作为确定结论输出。

## 5. 提交前体检（每次必做）

```bash
# ① 大文件检查：输出 OK 才允许提交
python -c "import subprocess,os;fs=subprocess.check_output(['git','ls-files','-z']).decode().split(chr(0));big=[(round(os.path.getsize(f)/1048576,1),f) for f in fs if f and os.path.exists(f) and os.path.getsize(f)>5*1048576];print(big if big else 'OK')"

# ② 密钥检查：不得有任何输出
git ls-files | grep -i -E "\.env$|key|token|secret"
```

GitHub 单文件上限 100MB，本地模型（bge-base-zh 约 390MB、bge-reranker 约 1.06GB）**永远不入库**，改用 `huggingface-cli` 下载。

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| push 被拒（main 受保护） | 正常，走分支 + PR |
| push 被拒（远端有新提交） | 先 `git pull --rebase` 再 push |
| 误 add 了大文件，未 commit | `git rm --cached -r <路径>` 后重新提交 |
| 大文件已 commit，未 push | `git reset --soft HEAD~1`，修 `.gitignore` 后重提 |
| 大文件 / 密钥已 push | 立即作废密钥；历史清理用 `git filter-repo` 或 BFG，**操作前务必沟通，勿自行强推** |
| CSV 冲突 | 用 VS Code 打开冲突文件，通常可选「保留双方更改」，再按 `诗歌ID` 去重 |

## 7. 提交信息前缀

`feat:` 新能力 ｜ `fix:` 修缺陷 ｜ `data:` 语料变更 ｜ `docs:` 文档 ｜ `refactor:` 重构 ｜ `chore:` 依赖与环境

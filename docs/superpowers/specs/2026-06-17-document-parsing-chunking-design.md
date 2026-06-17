# 文档解析与切块 — 设计文档

日期：2026-06-17
板块：后端「文档解析与切块」（todo.md 第 3 节）
分支：`feat/backend`

## 1. 定位与边界

纯解析库。输入 = 文件路径（或目录）；输出 = 带来源元数据的 `Chunk` 对象列表。

**不做**：不碰 Neo4j、不碰 embedding、不接 HTTP。Neo4j 写入与 embedding 留给后续板块。这条边界让本板块逻辑纯粹、最好测。

**输入类型（四类一次做齐）**：

- Markdown（`.md` / `.markdown`）
- 纯文本（`.txt`）
- PDF（`.pdf`，PyMuPDF，文本型）
- GitHub 仓库目录导入（遍历目录，对支持的文件批量解析）

**关键决策（brainstorming 收敛结论）**：

- 切块策略 = 结构感知切分（按自然边界切，超长再按字符上限拆分）。
- provenance 粒度 = 字符偏移 `[start, end)` + PDF 页码 + Markdown 标题路径。
- chunk 尺寸单位 = 字符数（不引 tokenizer、不绑厂商）。

## 2. 模块结构

新增 `backend/app/parsing/` 包：

```
backend/app/parsing/
├── __init__.py          # 对外导出 parse_file / parse_directory
├── models.py            # ParsedDocument, Block, Chunk, SourceLocation（Pydantic）
├── base.py              # 统一 parser 协议 + 按扩展名分派
├── markdown_parser.py   # .md/.markdown → Block 列表（带标题路径）
├── text_parser.py       # .txt → Block 列表（按空行分段）
├── pdf_parser.py        # .pdf → Block 列表（PyMuPDF，带页码）
├── chunker.py           # Block 列表 → Chunk 列表（结构感知 + 上限拆分 + 重叠）
└── repo_importer.py     # 目录遍历 → 对每个支持的文件调 parse_file
```

### 两段式数据流

```
文件 ──parser──> ParsedDocument(raw_text, blocks[]) ──chunker──> Chunk[]
```

- **parser 层**：每种格式只负责「抽出纯文本 + 切成带位置的语义块（Block）」。Block 是中间产物，带它在原文的字符偏移、（PDF）页码、（Markdown）标题路径。
- **chunker 层**：格式无关。吃 Block 列表，按语义边界聚合成目标大小的 chunk，超长 Block 再按字符上限 + 重叠拆分。

**为什么这样分**：解析（格式相关、脏活）与切块（格式无关、策略性）彻底解耦——换 chunking 策略不动任何 parser；加新格式（如未来 docx）只写一个新 parser，chunker 不变。对应规划「PDF 解析层保留扩展口」。

## 3. 数据模型（`parsing/models.py`，全部 Pydantic）

### SourceLocation — provenance 核心，每个 chunk 一份

```
document_id: str          # 来源文件标识（本板块用相对路径或文件名）
char_start: int           # 在该文档 raw_text 中的起始偏移（含）
char_end: int             # 结束偏移（不含），[start, end)
page: int | None          # PDF 页码（1-based）；非 PDF 为 None
heading_path: list[str]   # Markdown 标题层级路径，如 ["安装", "依赖"]；无则空列表
```

### Block — parser 输出的中间语义块（不直接出库，喂给 chunker）

```
text: str
char_start: int
char_end: int
page: int | None
heading_path: list[str]
```

### Chunk — 本板块最终产物

```
chunk_index: int          # 在所属文档内的顺序号，0-based
text: str
location: SourceLocation
char_count: int           # = len(text)，冗余存便于下游与评估
```

### ParsedDocument — 一次 parse_file 的完整结果

```
document_id: str
source_path: str          # 原始文件路径
doc_type: str             # "markdown" | "text" | "pdf"
raw_text: str             # 解析出的全文（偏移量都相对它）
chunks: list[Chunk]
```

### 取舍说明

- **document_id**：本板块不落库，先用「相对 samples/ 的路径」或文件名当 id；真正的持久化 id 留到 Neo4j 板块定，这里不冻结。
- **不存 token_count**：字符数单位，不引 tokenizer。
- **raw_text 留在 ParsedDocument**：偏移量相对它，下游验证「偏移能切回原文」需要它；不为每个 chunk 复制原文。
- **重叠区偏移**：相邻 chunk 因 overlap 会有偏移重叠，这是预期的——`char_start/end` 始终指向原文真实区间，前端高亮取并集即可。

## 4. chunker 切分算法（`parsing/chunker.py`）

**输入**：某文档的 `Block[]`（按出现顺序）+ 配置 `max_chars` / `overlap_chars` / `min_chars`。
**输出**：`Chunk[]`。

**配置默认值**（模块常量，可传参覆盖；不进 .env，因为是解析策略不是部署配置）：

- `max_chars = 800` — chunk 字符上限
- `overlap_chars = 150` — 相邻 chunk 重叠
- `min_chars = 100` — 小块合并阈值

### 算法三步

**第 1 步 — 超长 Block 预拆**
遍历 Block。若某 Block 的 `text` 长度 > `max_chars`，按 `max_chars` 步长、`overlap_chars` 重叠滑窗拆成多个子块。拆分时优先在窗口内**最后一个自然断点**（句号 / 换行 / 空格）回退切，避免切断词句；找不到断点才硬切。子块继承父 Block 的 `page` / `heading_path`，`char_start/end` 按真实偏移重算。

**第 2 步 — 聚合相邻块**
顺序累积块，只要「当前累积长度 + 下一块 ≤ `max_chars`」就合并进同一 chunk。**边界守卫**：仅当两块 `page` 相同且 `heading_path` 相同才合并——避免一个 chunk 跨页或跨标题，污染 provenance。遇到不同页 / 不同标题就收尾当前 chunk、另起一个。

**第 3 步 — 小块回填**
若收尾的 chunk < `min_chars`，尝试并入前一个 chunk（仍受 `max_chars` 和同页同标题守卫约束）；无法并入就保留为独立小 chunk（如文档结尾的短段）。

### overlap 取舍

聚合后 chunk 的 `char_start` = 首块起点，`char_end` = 末块终点。第 1 步滑窗产生的 overlap 体现在子块偏移区间天然重叠；**聚合层不再额外加 overlap**——overlap 只在「单个超长 Block 内部」发生，跨 Block 聚合靠自然边界，不人为重叠。理由：结构感知切分已用自然边界保证语义完整，跨段再加重叠收益小，且会让偏移区间互相纠缠、复杂化引用高亮。

## 5. 各 parser 实现要点

**统一协议（`base.py`）**：每个 parser 是函数 `parse(path) -> tuple[str, list[Block]]`，返回 `(raw_text, blocks)`。`base.py` 按扩展名分派到对应 parser，组装 `ParsedDocument`，再交给 chunker 填 `chunks`。对外只暴露 `parse_file(path)` 和 `parse_directory(path)`。

### text_parser.py（.txt）

- 读全文为 `raw_text`（UTF-8，失败回退 `errors="replace"`）。
- 按**连续空行**分段，每段一个 Block；`char_start/end` 用段在 raw_text 的真实偏移；`page=None`，`heading_path=[]`。

### markdown_parser.py（.md/.markdown）

- `raw_text` = 原始 Markdown 全文（不渲染、不剥语法——保留原文才能保证偏移可追溯）。
- 扫描行首 `#`/`##`/… 维护**标题栈**，得到每段的 `heading_path`。
- 按标题行和空行切段成 Block，标题行本身归入其后正文的同一 heading_path。`page=None`。
- 纯文本扫描实现，**不引 markdown 渲染库**——只认标题层级，够用且零依赖。

### pdf_parser.py（.pdf，PyMuPDF）

- 用 `fitz` 逐页 `page.get_text("text")`。
- `raw_text` = 各页文本按页序拼接（页间插一个 `\n`，记录每页在 raw_text 的起始偏移，用于算 Block 偏移）。
- 每页内按空行分段成 Block，`page` = 该页页码（1-based），`heading_path=[]`。
- **扫描版 PDF**：若某页 `get_text` 返回空 / 近空，记一条 warning（该页无文本层），**不报错、不做 OCR**——对应规划「OCR 不作核心验收，但保留扩展口」。

### repo_importer.py（目录导入）

- 递归遍历目录，按扩展名筛 `.md/.markdown/.txt/.pdf`。
- **跳过**：`.git`、`node_modules`、`__pycache__`、`.venv` 等常见噪音目录（一个小的忽略集合）。
- 对每个命中文件调 `parse_file`，汇总成 `list[ParsedDocument]`。
- 单个文件解析失败：记录错误并跳过，不中断整批。

### 依赖

新增 `PyMuPDF`。本板块到实现阶段先征求同意再在 myself 环境安装（遵守 CLAUDE.md「需安装新依赖务必先询问」）；现在只在 `requirements.txt` 登记。

## 6. 错误处理

分层，区分「硬失败」和「软降级」：

- **硬失败（抛异常）**：文件不存在、扩展名不支持、PDF 文件损坏无法打开。`parse_file` 抛 `ParseError`（本包自定义异常，带 path 和原因）。调用方决定怎么呈现。
- **软降级（记 warning 继续）**：PDF 某页无文本层（扫描页）、文本编码异常（回退 replace）、空文件（返回空 chunk 列表而非报错）。用标准 `logging`，复用项目已有的 `logging_conf`。
- **目录导入**：单文件硬失败被 `repo_importer` 捕获 → 记 error 日志 + 跳过，整批不中断。

**为什么这样分**：解析库是底层，不该吞掉「用户给错文件」这类调用方必须知道的错；但也不该因「一份扫描 PDF 的一页没文字」就让整个导入崩掉。硬失败往上抛、软问题往日志降级。

## 7. 测试策略（pytest，`backend/tests/`）

构造**最小自带 fixture 文件**（不依赖外部样本，测试自包含、可复现）：

| 测试 | fixture | 验证点 |
|---|---|---|
| txt 解析 | 两段空行分隔的 .txt | Block 数、偏移区间、`page=None` |
| Markdown 标题路径 | 含 `#`/`##` 多级标题的 .md | `heading_path` 正确、跨标题不合并 |
| PDF 解析 | 测试内用 PyMuPDF 现生成 2 页 PDF | 页码正确、`raw_text` 含两页内容 |
| chunker 超长拆分 | 构造 > max_chars 的单 Block | 子块数、overlap 重叠、自然断点回退 |
| chunker 同页同标题守卫 | 跨页 / 跨标题的 Block 列表 | 不跨边界合并 |
| **偏移可追溯（核心）** | 任意 fixture | 断言 `raw_text[chunk.char_start:chunk.char_end]` 能还原 chunk 文本 |
| 目录导入 | 临时目录放 .md + .txt + 一个 .git 子目录 | 命中正确文件数、跳过 .git |
| 不支持的扩展名 | .xyz 文件 | 抛 `ParseError` |

**最关键的验证**是「偏移可追溯」断言——直接对应「引用必须能落到原始 chunk」的硬要求，是本板块核心成功标准。

## 8. 验收对齐（todo.md 本板块验证项）

- ✅ 样本文档能解析成稳定 chunk → 各 parser 测试
- ✅ 每个 chunk 能追溯到来源文档 → 偏移可追溯断言 + `document_id`
- ✅ PDF 样本解析结果可用 → PDF 解析测试

## 9. 不在本板块范围（明确划出）

- Neo4j 写入 Document/Chunk（下一板块）
- embedding 生成与向量索引（下一板块）
- HTTP 上传接口 `POST /api/documents`（后续板块）
- docx / html 解析（工程扩展点，预留不实现）
- 扫描版 PDF 的 OCR（保留扩展口，不实现）
- token 级尺寸计量（已定用字符数）

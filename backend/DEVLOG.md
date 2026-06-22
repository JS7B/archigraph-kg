# 后端学习记录（DEVLOG）

## 2026-06-17 后端 FastAPI 骨架搭建

- 做了什么：搭起 `backend/` 的 FastAPI 应用骨架——配置、日志、统一错误、Neo4j/LLM 客户端薄封装、健康检查路由与测试，跑通 `/health` 与 `/health/deps`。

- 这是什么：
  - **FastAPI** 是一个 Python Web 框架，用来把函数暴露成 HTTP 接口。你写一个普通函数，加个装饰器（如 `@router.get("/health")`），它就变成一个网页地址能访问的接口，并自动帮你做参数校验、生成文档。
  - **pydantic-settings** 是“配置读取器”。它把 `.env` 文件里的环境变量（如 `NEO4J_PASSWORD=...`）自动映射成一个 Python 对象的字段，省去手写 `os.getenv` 和类型转换，还能集中管理。
  - **lifespan** 是 FastAPI 的“开机/关机钩子”。应用启动时跑一段代码、关闭时跑另一段。我们用它在启动时建好 Neo4j 连接、在关闭时干净地断开，避免连接泄漏。
  - **Neo4j driver（驱动）** 是连接 Neo4j 图数据库的客户端对象。它内部维护一个连接池，整个应用共享一个 driver 就够了，不必每次查询都重新连。

- 为什么需要：这是后端的“地基”。后面所有功能（文档解析、抽取、图谱构建、检索问答）都挂在这套骨架上。先把“怎么读配置、怎么连数据库、出错怎么统一返回、怎么自检健康状态”这几件事固定下来，后续写业务逻辑时就不用反复操心基础设施。`/health` 还能让部署后一眼确认“服务活着没”，`/health/deps` 确认“依赖（Neo4j/LLM）通不通”。

- 为什么这么做（分层理由）：
  - **config / clients / routers 分开**：配置只管“从哪读、读什么”；clients 只管“怎么和外部系统（Neo4j、LLM）说话”；routers 只管“对外暴露哪些接口”。三者职责单一，改一处不牵连另两处——比如以后换 LLM 厂商，只动 `clients/llm.py`，路由和配置都不用碰。
  - **配置全走环境变量、零硬编码**：密钥、地址、模型名都从 `.env` 读，代码里不写任何真实值。这样公开仓库不会泄密，换环境也只改 `.env`。`get_settings()` 用 `lru_cache` 缓存，保证全程只读一次 `.env`、只有一个配置实例。
  - **`/health` 与 `/health/deps` 拆成两个**：前者绝不依赖外部、永远通，用于“进程活着吗”；后者探测 Neo4j 和 LLM，且把任何失败**降级成文本**（如 `"error: ..."`）而不是抛 500——探针自己不能因为依赖挂了就崩，否则没法用它来诊断。
  - **统一错误结构**：所有异常都包成 `{"error": {"type", "message"}}`，前端拿到的错误格式永远一致，不用对每种报错单独适配。
  - **LLM 用 OpenAI-compatible 接口**：用 `openai` 库 + 自定义 `base_url`，这样任何兼容 OpenAI 协议的服务商都能接，不锁死单一厂商。`is_configured()` 通过识别 `.env.example` 里的占位标记（`your-` / `please-change`）判断是否填了真实值，骨架阶段不真的去调 LLM，避免占位 key 报错。

- 踩了什么坑：
  - **neo4j 6.x 的连通性探测写法**：本机装的是 neo4j 6.2.0。早期教程里 `driver.verify_connectivity()` 在不同版本行为/可用性有差异，这里直接用更稳的 `driver.execute_query("RETURN 1")`——能跑通就说明连接、认证、查询全链路 OK，语义比单纯握手更可靠。
  - **driver 是“懒连接”**：`GraphDatabase.driver(...)` 这一步并不会立刻连数据库，真正建连接发生在第一次执行查询时。所以 lifespan 里建 driver 不会因为 Neo4j 没起来而失败，连不上的暴露点统一落在 `/health/deps` 的 `execute_query`，正好被它的 `try/except` 接住降级——测试因此不依赖真实 Neo4j 也能过。
  - **worktree 没有 .env**：当前在隔离的 git worktree 里工作，仓库根没有 `.env`。按要求从 `.env.example` 复制了一份测试用 `.env`（把 `NEO4J_PASSWORD` 改成本机 Neo4j 容器的密码 `TestPass12345`，LLM 字段保持占位），验证完毕。`.env` 已被 `.gitignore` 忽略，不会误提交。

## 2026-06-18 文档解析与切块

- 做了什么：实现纯解析库 `app/parsing/`——txt/Markdown/PDF 单文件解析 + GitHub 目录导入，统一产出带来源元数据（字符偏移 + 页码 + 标题路径）的 Chunk 列表。两段式：parser 抽文本切语义块，chunker 聚合 + 超长拆分。全套 TDD，全量回归 43 passed。

- 这是什么：
  - **chunk（切块）**：把长文档切成小片段，是后续向量检索和 GraphRAG 的最小证据单元。切太大检索不准、切太小丢上下文，所以要按语义边界切并控制大小。
  - **provenance（来源追溯）**：每个 chunk 记住它在原文的精确位置（第几个字符到第几个字符、第几页、哪个标题下），这样回答引用时能定位回原文高亮，是本项目「引用可追溯」硬要求的地基。
  - **PyMuPDF（fitz）**：一个 PDF 文本抽取库，逐页拿出文字层。扫描版 PDF 没有文字层（只有图片），它拿不到文本——我们只记 warning 不做 OCR。

- 为什么需要：所有下游能力（图谱、检索、问答）都吃 chunk。没有稳定、可追溯的 chunk，后面全都立不住。

- 为什么这么做（关键取舍）：
  - **parser 与 chunker 解耦**：解析是格式相关的脏活，切块是格式无关的策略。分开后换切块策略不动 parser，加新格式只写新 parser。
  - **偏移单位用字符不用 token**：token 计数要 tokenizer，会绑定具体模型、加依赖；本项目不绑厂商，字符数最简单稳定。
  - **核心不变量 `raw_text[start:end] == chunk.text`**：每个 parser 和 chunker 都有测试断言它，这是「引用能落回原文」的机器化保证。
  - **全短段落文档无 chunk 间 overlap（有意决策，备查）**：overlap 只在「单个超长 Block 内部滑窗」时产生；若文档全是短段落，聚合路径不人为加重叠。理由：结构感知切分已用自然边界保证语义完整，跨段再加重叠收益小，还会让偏移区间互相纠缠、复杂化引用高亮。若后续评估发现召回因缺重叠而变差，再在聚合层引入可配置 overlap。
  - **chunker 不做小块回填（规划阶段砍掉的死代码）**：原计划有「小尾块并入前块」的第 3 步，落地前审查发现它与「贪心聚合 + 同页同标题守卫」的条件完全重叠——能并的在聚合阶段就并了，跨页/跨标题的小块用同样守卫照样并不了。回填永不触发，且若强行跨边界并入会污染 provenance，与「引用优先」冲突。故删除。教训：动手前推演控制流，能在写代码前砍掉死逻辑。
  - **Markdown 标题文字只计入正文块一次**：标题行与其后正文合为同一 Block，不单独成块，避免标题在 chunk 里重复。

- 踩了什么坑：
  - **本机有两个 Python**：系统默认 `python` 是 3.14（没装项目依赖，连 pytest 都没有），项目依赖全在 conda `myself` 环境（3.12）。跑测试必须显式 `conda run -n myself python -m pytest`，否则报 `No module named pytest`。这是「环境隔离」的典型表现——别假设 `python` 指向你想要的那个。
  - **PyMuPDF 包名与导入名不一致**：pip 装的是 `PyMuPDF`，代码里却 `import fitz`。这是历史遗留命名，记住「装 PyMuPDF、导 fitz」即可。

## 2026-06-18 Neo4j 图谱写入与向量检索

- 做了什么：新增 `app/graph/` 写入与检索层——建图谱约束与向量索引（`schema.py`）、把文档与 chunk 落库并写入 embedding（`writer.py`/`embedding.py`）、按问题向量召回 top-k 相关 chunk（`search.py`）。10 个集成测试连真实 Neo4j 全通，真实 embedding（text-embedding-3-large，3072 维）端到端召回验证成功。

- 这是什么：
  - **embedding（向量嵌入）**：把一段文本压成一串定长数字（这里 3072 个），语义相近的文本，向量也相近。它和「切分」无关——切分早已用纯规则做完；embedding 是为了「检索」：提问时把问题也转成向量，找数学上最接近的 chunk。
  - **向量索引（Vector Index）**：Neo4j 5.13+ 自带的能力，把所有 chunk 的向量建成一个可快速搜索的结构（HNSW 图），让「找最相似的 k 个」从逐个比对变成近似最近邻查询，量大时快得多。无需 APOC/GDS 插件。
  - **余弦相似度（cosine）**：衡量两个向量「方向」是否一致的指标，1 最像、0 不相关。文本检索常用它而非欧氏距离，因为只关心语义方向、不关心向量长度。
  - **MERGE（幂等写入）**：Cypher 的「有则匹配、无则创建」。我们给每个 chunk 造确定性的 `chunk_id = 文档id#序号`，重复入库同一文档时 MERGE 命中老节点、不会产生重复——这让「重新处理一篇文档」是安全的。

- 为什么需要：解析切块产出的 chunk 此前只在内存里，不能检索。这一层是 GraphRAG 的地基——把 chunk 连同来源位置和向量一起存进 Neo4j，提问时才能「先向量召回相关片段，再顺着图谱扩展」，并且每个召回结果都带得回 `document_id + 字符偏移 + 页码 + 标题路径`，满足「引用可追溯」这条硬规则。

- 为什么这么做（分层理由）：
  - **`clients/graph.py` 只管驱动生命周期，业务读写单独成 `app/graph/`**：连接管理（建/探/关）和「写什么图、怎么查」是两件事，分开后换 schema 不动连接、换连接不动业务。
  - **不为 Document/Chunk 另造 pydantic 模型**：直接复用解析层的 `ParsedDocument`/`Chunk`/`SourceLocation` 作写入入参，避免同一份数据有两套模型来回转换。只为「查询结果」新增 `ChunkHit`（多一个 score 字段，是新形状）。
  - **维度（EMBEDDING_DIM）走配置、不硬编码**：换 embedding 模型维度就变（3-large=3072、ada-002=1536）。同一个配置值既喂给「建索引」也喂给「写入前校验」，保证两者永远一致；写入前逐条校验向量长度，维度不符直接报错，避免脏数据进库后查询才崩。
  - **schema 初始化放 lifespan 且失败只告警**：约束/索引都用 `IF NOT EXISTS`，重复启动无副作用；Neo4j 没起来时只 warning 不阻断 FastAPI 启动，和 `/health/deps`「依赖挂了也不崩」的哲学一致。

- 踩了什么坑：
  - **向量索引建好后不是立刻能查**：`CREATE VECTOR INDEX` 后索引在后台异步构建（POPULATING），此时查询会抛 `51N63`。必须 `CALL db.awaitIndexes(120)` 等它变 ONLINE 再用。
  - **索引维度不能用 Cypher 参数**：`OPTIONS {indexConfig:{...}}` 里的维度在「规划期」求值，不接受 `$dim` 绑定，只能把数字插值进 DDL 字符串。因维度来自可信的整数配置（非用户输入），插值是安全的。
  - **共享库下的索引维度冲突**：所有 worktree 连同一个 Neo4j、同一个数据库，向量索引名又固定。生产用 3072 维，但集成测试为了快用 8 维合成向量——测试 fixture 必须先 `DROP INDEX ... IF EXISTS` 再以测试维度重建，跑完真实数据前再恢复 3072。这是「同容器同库跨 worktree 共享」约定的真实代价，并行写图谱要错峰。
  - **`conda run` 不支持多行 `python -c`**：临时探测/冒烟脚本要写成 `.py` 文件再 `conda run -n myself python 文件`，不能把带换行的代码塞进 `-c`（会报 NotImplementedError）。

## 2026-06-18 实体识别与关系抽取

- 做了什么：新增 `app/extraction/` 抽取层——逐 chunk 调 LLM（JSON 模式）抽实体与关系、文档内按名称归一合并去重、写入 Neo4j（`MENTIONS` / `RELATES`）。22 个测试全通（含真实 LLM 抽取），端到端冒烟从一篇文档抽出 12 实体 / 10 关系，关系证据全部能落回 chunk。

- 这是什么：
  - **结构化抽取（structured extraction）**：让大模型不是返回一段话，而是返回固定格式的 JSON（这里是 `{entities:[...], relations:[...]}`），程序能直接解析成对象。我们用 OpenAI 接口的 `response_format={"type":"json_object"}`（即「JSON 模式」）强制模型只吐 JSON，再用 Pydantic 校验字段，省去从自由文本里抠数据。
  - **实体 / 关系 / Mention**：实体是文档里的关键对象（如 FastAPI、Neo4j）；关系是实体间的语义连接（如「FastAPI 依赖 Pydantic」）；Mention 是「某实体在某个 chunk 里出现过」这件事，在图里就是 `(:Chunk)-[:MENTIONS]->(:Entity)` 这条边——它把抽象实体接回原文，是「引用可追溯」的基石。
  - **实体合并去重**：同一篇文档里，不同 chunk 可能都提到「FastAPI」，抽出来就是多个实体对象。合并就是把「归一化名（小写去空格）+ 类型」相同的认作同一个实体，mention 累积、描述合并，只在图里建一个节点。

- 为什么需要：上一板块只把 chunk 和向量存进了图，图里还没有「知识」。抽取这一步把文本里的实体和关系结构化出来连成网，GraphRAG 问答时才能「先向量召回 chunk，再顺着实体关系扩展邻域」。每条关系都带 `evidence_chunk_id`，保证答案里引用的关系能回溯到原文，满足硬规则。

- 为什么这么做（关键取舍）：
  - **用 JSON 模式而非 function calling**：两者都能拿结构化输出，但 JSON 模式更简单、对 OpenAI-compatible 第三方端点兼容性更好（实测 deepseek/qwen/glm 都支持）。代价是要在 prompt 里显式出现「json」字样（JSON 模式的硬性要求），否则部分服务端会报错——所以 system 和 user 文案都写了 JSON，并用单测 `test_prompt` 守住这条不被人误删。
  - **逐 chunk 抽取**：每个 chunk 单独调一次 LLM，mention 天然精确到 chunk（这条 chunk 抽出的实体，证据就是这条 chunk）。代价是调用次数多；但换来引用可追溯最稳，跨 chunk 的重复实体留到合并阶段统一处理。
  - **名称归一精确合并（不做向量近义合并）**：先用最简单可靠的「归一名+类型相等」合并，跑通主链路。近义词合并（如 K8s=Kubernetes）更准但要额外调 embedding、引入误合并风险，等评估阶段确有需要再加——符合「先简单、再按需」。
  - **业务关系统一落 `:RELATES`、类型作属性**：所有关系在 Neo4j 里都是 `:RELATES` 这一种边，具体语义（依赖/使用/组成…）放在 `type` 属性里。这样图 schema 稳定、查询统一，等样本和评估稳定后再判断是否要拆成独立边类型。
  - **单 chunk 失败不中断整文档**：某个 chunk 多次抽取失败就记录错误跳过（沿用目录导入的容错风格），返回统计里带 `failed_chunks`，避免一颗老鼠屎坏一整锅。
  - **抽取层与图谱写入层解耦**：`extract_and_ingest` 假定 Document/Chunk 已由上一板块 `ingest_document` 写好，自己只写 Entity/MENTIONS/RELATES；MENTIONS 用 `MATCH` 找 chunk（不 `MERGE`），避免凭空造出孤立 Chunk 节点。

- 踩了什么坑：
  - **JSON 模式必须 prompt 里有「json」字样**：OpenAI 的 json_object 模式有个硬性约束——请求消息里必须出现「json」这个词，否则端点直接报错。容易在改文案时不小心删掉，所以加了单测锁定。
  - **关系两端实体名可能对不上**：LLM 在 relations 里写的 source/target 是实体名，偶尔和 entities 里的名字大小写/写法不一致，或指向没抽出来的实体。合并层的策略是：解析不到就**丢弃这条关系并告警**，绝不建一条指向空节点的脏边。
  - **Entity 必须带 document_id**：测试清理是按 `document_id STARTS WITH 'test_'` 删节点，Entity 若不存 document_id 就会被漏删，污染跨 worktree 共享的同一个库。写图时强制 SET 了 document_id。
  - **conda run 不支持多行 `python -c`**：和上一板块一样，临时冒烟脚本要落成 .py 文件再 `conda run -n myself python 文件` 跑。

## 2026-06-22 GraphRAG 检索与回答

- 做了什么：新增 `app/qa/` 问答编排层，把前三个板块（向量召回+实体关系图谱）串成 GraphRAG 问答：问题 embedding → 向量召回 chunk → reranker 重排 → 1 跳实体邻域扩展 → 组装上下文 → LLM 生成带引用答案。暴露 `POST /api/chat` 与 `GET /api/chunks/{id}`。全链手写，不引第三方 GraphRAG 框架。测试 18 个全通，端到端问答冲烟答案准确且引用全部可回链。

- 这是什么：
  - **GraphRAG**：在普通向量检索（RAG）基础上，额外利用知识图谱的实体关系。召回到相关 chunk 后，顺着「这些 chunk 提到了哪些实体」、「这些实体又和谁有关系」扩展，把图谱里的结构信息一起喞给 LLM，答得更全面。
  - **reranker（重排模型）**：向量检索快但粗（只看语义方向）；重排模型（bge-reranker-v2-m3）拿问题和每个 chunk 逐一精算相关分，把最相关的提到前面。先向量召回宽一点（top 10）再用 reranker 筛出 top 5，准又不浪费算力。
  - **带引用答案**：把召回的 chunk 编号 [1][2]…喞给 LLM，要求它每句论断都标上来源角标。答案里的 [n] 能顺着 Citation 找回具体 chunk 原文——这就是「引用可追溯」。

- 为什么需要：前三个板块把知识存进了图，但还不能回答问题。这一层才是项目的核心价值：让用户问一句，系统从图谱里找证据、生成可追溯到原文的答案。

- 为什么这么做（关键取舍）：
  - **纯手写 Cypher，不引 neo4j-graphrag/langchain/llamaindex**：调研过四个主流方案。结论是——手写 `CALL db.index.vector.queryNodes` + 几句图遍历 Cypher，和 neo4j-graphrag 的 retriever 底层做的是同一件事，但零新增依赖、编排 100
## 2026-06-22 GraphRAG 检索与回答

- 做了什么：新增 `app/qa/` 问答编排层，把前三个板块（向量召回 + 实体关系图谱）串成 GraphRAG 问答：问题 embedding → 向量召回 chunk → reranker 重排 → 1 跳实体邻域扩展 → 组装上下文 → LLM 生成带引用答案。暴露 `POST /api/chat` 与 `GET /api/chunks/{id}`。全链手写，不引第三方 GraphRAG 框架。测试 18 个全通，端到端问答冒烟答案准确且引用全部可回链。

- 这是什么：
  - **GraphRAG**：在普通向量检索（RAG）基础上，额外利用知识图谱的实体关系。召回到相关 chunk 后，顺着「这些 chunk 提到了哪些实体」「这些实体又和谁有关系」扩展，把图谱里的结构信息一起喂给 LLM，答得更全面。
  - **reranker（重排模型）**：向量检索快但粗（只看语义方向）；重排模型（bge-reranker-v2-m3）拿问题和每个 chunk 逐一精算相关分，把最相关的提到前面。先向量召回宽一点（top 10）再用 reranker 筛出 top 5，准又不浪费算力。
  - **带引用答案**：把召回的 chunk 编号 [1][2]… 喂给 LLM，要求它每句论断都标上来源角标。答案里的 [n] 能顺着 Citation 找回具体 chunk 原文——这就是「引用可追溯」。

- 为什么需要：前三个板块把知识存进了图，但还不能回答问题。这一层才是项目的核心价值：让用户问一句，系统从图谱里找证据、生成可追溯到原文的答案。

- 为什么这么做（关键取舍）：
  - **纯手写 Cypher，不引 neo4j-graphrag/langchain/llamaindex**：调研过四个主流方案。结论是——手写 `CALL db.index.vector.queryNodes` + 几句图遍历 Cypher，和 neo4j-graphrag 的 retriever 底层做的是同一件事，但零新增依赖、编排 100% 自控。其他框架要么太重（langchain 拉 15-25 个包）、要么太黑盒（微软 GraphRAG 要求自己的 parquet 管道，不对接现有图）、要么与 neo4j driver 6.x 版本冲突（llamaindex）。这正是 CLAUDE.md「保留编排控制权 + 极简依赖」决策边界的落地。
  - **1 跳邻域而非多跳**：只扩 1 跳（chunk→实体→邻居实体）。多跳会图爆炸、引入噪声，先拿最简的稳定版。
  - **引用只保留答案里真实出现的角标**：LLM 可能给了上下文但没全用。解析答案文本里实际出现的 [n]，只把被引用的 chunk 计入 citations，避免虚报引用。
  - **压幻觉**：system prompt 明确要求「只依据给定片段作答、无依据就说无法回答」，对齐「明显幻觉率 ≤ 20%」验收指标。
  - **rerank 失败降级不中断**：reranker 端点挂了就回退到按向量 score 取 top-N，问答照常跑。
  - **不落 Run/Answer 图节点**：本板块的 Answer 是 API 响应对象，引用靠 Citation.chunk_id 追溯；Run/RunEvent/Answer 节点持久化是下一个「Run 与事件流」板块的事，边界划清楚。

- 踩了什么坑：
  - **reranker 不走 OpenAI SDK**：openai 库只有 chat/embeddings，没有 rerank 端点。rerank 是各家自定义的 `POST /rerank`，用 httpx 直调；payload `{model,query,documents,top_n}`，返回 `results:[{index,relevance_score}]` 降序。
  - **TestClient 不触发 lifespan**：`TestClient(create_app())` 不会跑 lifespan，`app.state.neo4j` 是空的，路由里 `request.app.state.neo4j` 报 AttributeError。解法：测试里手动 `app.state.neo4j = driver` 注入现有 driver（不走 lifespan、不重建 schema）。
  - **真实 3072 维与测试 8 维冲突**：API 集成测试里向量召回部分 monkeypatch 掉（召回本身 graph 板块已测），只让真实 rerank+chat 跑，避开维度冲突。

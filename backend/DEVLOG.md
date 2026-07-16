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


## 2026-06-22 文档上传入库 HTTP API（A 板块）

- 做了什么：新增 `app/routers/documents.py`，把已完成的解析→embedding→写图→抽取链路用一个 HTTP 端点串起来。`POST /api/documents` 接收 multipart 上传，同步跑完整入库，返回结果摘要（documentId/chunkCount/extraction 统计）；`GET /api/documents` 列表、`GET /api/documents/{id}` 单文档详情直接查 Neo4j Document 节点。ingest_document 写入时顺带落状态字段（parse_status/index_status/chunk_count/name/source_type），供前端徽标。测试 10 passed + 1 skipped（无 PDF 样本）。

- 这是什么：
  - **multipart/form-data 上传**：HTTP 传文件的标准方式——请求体被切成多段（boundary 分隔），一段是文件内容、一段是表单字段。FastAPI 用 `UploadFile` 类型声明参数，自动解析。底层依赖 `python-multipart` 库（FastAPI 官方依赖）。
  - **同步入库链路**：一个请求里跑完 parse→embed→ingest→extract 全流程才返回。简单直接，但请求耗时长（大文档会阻塞）。按大脑裁决，异步化（Run/SSE）留给 B 板块，A 先同步打通。

- 为什么需要：前端现在全跑在 mock 数据上，三视图（文档库/图谱/工作台）看不到真实内容。这个端点一通，前端就能真正上传文档、触发入库、看到文档列表——从假数据切到真链路的第一步。

- 为什么这么做（关键取舍）：
  - **document_id 用源文件名，不是临时文件名**：上传文件先落临时盘（`NamedTemporaryFile`）让 parser 按文件读。但 `parse_file` 缺省用 `os.path.basename(path)` 当 document_id——若传临时路径，document_id 就是 `upload_xxxx.md`，同文件重复上传会因临时名不同而产生不同 id，**破坏 chunk_id 幂等**（chunk_id = document_id#chunk_index）。所以路由显式传 `document_id=源文件名`，保证幂等。
  - **同步而非异步**：大脑裁决（backend-ruling-ab-split.md）——A 小而独立、可立刻验证；异步 Run/SSE 涉及前端契约变更和更大 review 风险，拆到 B 板块单独做。符合 CLAUDE.md「简单优先」。
  - **状态字段顺带写 Neo4j，不另建表**：前端 DocumentMeta 需要 parseStatus/indexStatus/chunkCount 做徽标。Document 节点本身就在图库里，写入时顺手 SET 这些属性，GET 直接查图库即可，无需额外的状态表。
  - **临时文件 try/finally 清理**：入库链路任一步可能抛异常，finally 块确保临时文件无论成败都删，不留在磁盘。测试里 mock `os.remove` 验证清理确实发生。

- 踩了什么坑：
  - **Pydantic v2 alias 模型要用 snake_case 构造需配 populate_by_name**：响应模型用 `Field(alias="entityCount")` 输出 camelCase，但内部代码用 `entity_count=...` 构造时 Pydantic v2 默认只认 alias，报 `Field required`。解法：`model_config = ConfigDict(populate_by_name=True)`，既能 snake 构造又能 camel 输出。
  - **测试维度(8)与生产维度(3072)冲突**：路由调用 `ingest_document` 内部读 `get_settings().embedding_dim` 做维度校验（3072），但测试用 8 维占位向量。解法：测试 fixture 把配置实例的 `embedding_dim` 临时 monkeypatch 成 8（lru_cache 返回同一实例，可改属性），让 8 维向量通过校验并真实写入——写图逻辑本身不被 mock，仍走真实代码。
  - **modelverse API key 配额耗尽**：全量回归时 2 个真实 LLM gate 测试（test_llm_real / test_chat_api）因 key 日限额 1000 用尽返回 403。非本次改动问题，待配额恢复后补真实端到端冒烟。


## 2026-06-22 Run/事件流 + SSE + 异步化 + 图谱查询 API（B 板块）

- 做了什么：把 A 板块的同步上传/问答升级为异步——上传/问答/删除立即返回 `runId`，后台任务跑真实链路并 emit 进度事件，前端通过 SSE 订阅 `/api/runs/{runId}/events/stream` 拿实时进度（像素 Agent 动画由真实 `RunEvent` 驱动）。问答终态事件直接带 `answer`（方案 a，前端少一次往返）。另补齐前端 P3 的图谱查询 API（实体列表/邻域/搜索）。

- 这是什么：
  - **Run / RunEvent**：一次异步执行（入库/问答/删除）= 一个 Run，过程中的进度信号 = RunEvent。RunEvent 有 stage（12 个锁定值：idle/uploading/parsing/...）、status（running/succeeded/failed）、message、answer（仅问答终态）。前端像素 Agent 的状态机就靠这些 stage 驱动。
  - **SSE（Server-Sent Events）**：服务器单向推消息给浏览器的协议。`text/event-stream` 响应，每条消息 `data: {...}\n\n`。浏览器用 `EventSource` API 订阅。比 WebSocket 简单（单向够用），uvicorn 原生支持。
  - **BackgroundTasks**：FastAPI/Starlette 的后台任务机制——响应返回后异步执行。比 Celery/RQ 轻得多（单进程、不持久化、重启丢失），符合 CLAUDE.md「简单优先，先跑通再命名」。
  - **EventSourceResponse（sse_starlette）**：把一个 async generator 包成 SSE 响应，yield dict/str 就是一条 SSE 事件。

- 为什么需要：A 板块同步链路让前端能拿真实数据了，但前端三视图（尤其像素 Agent 动画 + RunEventTimeline）全部跑在 mock 事件上——CLAUDE.md 硬要求「像素 Agent 动画状态必须来自真实 RunEvent，不得用前端伪造状态驱动」。B 板块就是把「后端真实执行」翻译成「前端能消费的进度信号」的桥。不做它，前端动效永远是假的。

- 为什么这么做（关键取舍）：
  - **内存 RunStore，不持久化**：Run 是瞬态进度信号，重启丢失可接受——前端刷新会重新查 Document 状态（那部分落 Neo4j 了）。把 Run 存图库反而复杂化，且 SSE 读图库是反模式（每秒轮询）。CLAUDE.md「简单优先」。
  - **BackgroundTasks 而非 Celery**：单进程、单用户、演示场景够用。引入 Celery 要加 broker（Redis/RabbitMQ）、worker 进程、序列化，过度设计。决策边界明确允许「先用简单后台任务」。
  - **SSE 终态事件带 answer（方案 a）**：前端不用再发一次请求取答案，订阅 SSE 流到终态就拿到完整 answer。少一次往返、代码更简。
  - **chat 后台任务拆 answer_question 的内部步骤**：不整体调 answer_question，而是拆成 search→rerank→expand→build→chat，在每个里程碑 emit 事件（searching/checking/writing）。这样前端能看到检索的全过程，而非一个黑盒 loading。
  - **asyncio.Queue 做订阅**：每个 SSE 订阅者一个队列，append_event 时向所有队列投递副本。subscribe 时先投历史事件（不漏）。简单可靠。
  - **删除用纯 MENTIONS 关系判孤立实体**：Entity 不直接连 Document，孤立性 = 不再被任何 Chunk MENTIONS。最初我臆造了 MENTIONS_FROM_DOC 关系类型（不存在），核实真实关系后改对。

- 踩了什么坑：
  - **anyio 默认双 backend（asyncio+trio）**：`@pytest.mark.anyio` 会让测试在 asyncio 和 trio 两个 backend 各跑一次，trio 没装就虚假失败。解法：conftest 里把 `anyio_backend` fixture 固定为 `"asyncio"`。注意 `pytest.ini` 里写 `anyio_backend=` 不被 pytest 识别（anyio 读的是 fixture 不是 ini 选项）。
  - **chat.py 删除旧 import 后 QA 测试失效**：异步化后 chat.py 不再 import `answer_question`，旧的 `test_chat_api` 还 monkeypatch `answer_question`，且假设 POST 同步返回 answer。彻底更新该测试适配异步契约（mock run_chat emit 终态事件）。
  - **ChatResponse 缺 alias**：Pydantic 模型字段 `run_id` 默认序列化成 `run_id`，前端要 `runId`。需 `Field(alias="runId")` + `model_dump(by_alias=True)`。与 documents 路由同款坑。
  - **TestClient 不触发 lifespan**：`TestClient(app)` 不进 `with` 块就不跑 lifespan，`app.state.runs` 不存在。测试里手动注入 `app.state.runs = RunStore()` 和 `app.state.neo4j = driver`。
  - **modelverse API key 配额耗尽**：全量回归时 `test_llm_real` 因 key 日限额 1000 用尽返回 403，非本次改动问题。


## 2026-06-24 评估与质量保障 + run_chat bug 修复

- 做了什么：为本系统建了一套可复现的评估，量化 AGENTS.md 四项硬指标。4 篇样本取自本项目自带文档（规划/AGENTS/API契约/解析设计），人工标注 ground truth（实体/关系/问答），单脚本 `evals/run_eval.py` 跑全链路出报告。另顺手修了 `run_chat` 后台任务的一个真实 bug。

- 这是什么：
  - **评估（evaluation）**：给 AI 系统打分的方法论。光跑通不够，要用真实数据量化"它到底有多准"——召回率（该抽的抽到了吗）、命中率（引用对不对）、幻觉率（编没编）。这是 AI 项目从 demo 变成"可证明效果"的关键，也是简历硬通货。
  - **ground truth（标注真值）**：人手工标的"标准答案"。机器抽出的实体要和人标的比，才知道漏没漏。标注质量直接决定评估可信度。
  - **召回率 vs 准确率**：召回率=该找的找到了多少（漏没漏），准确率=找到的对不对（找错没）。评估抽取质量主要看召回率。

- 为什么需要：CLAUDE.md 把"不只是 demo，能证明效果"列为验收硬指标。没有评估，"实体抽取还行"只是主观感受；有评估，"召回率 78%、引用命中率 100%"才是可复现的工程证据。

- 为什么这么做（关键取舍）：
  - **样本用本项目自带文档**：零版权风险、零下载、现成。虽然不是真实论文，但覆盖技术规划/GitHub文档/API契约/设计规格四类，实体足够丰富，够证明指标可算可复现。
  - **document_id 用 eval_ 前缀**：Neo4j 跨 worktree 共享，评估数据用独立前缀，脚本跑完自动 `MATCH ... STARTS WITH 'eval_' DETACH DELETE`，不污染前端联调数据。
  - **调 extract_document + merge_extractions 而非 extract_and_ingest**：后者只返回统计数、丢弃合并后的实体对象。评估要拿实体算召回率，必须直接调前两个，避免重复 LLM 抽取（一次抽取既算指标又写图）。
  - **幻觉率半自动**：全自动判幻觉是开放难题（要理解"这句话有没有依据"）。半自动——机器按句切分、列出无角标引用的"可疑句"，人复核——诚实且可复现，符合交接清单"允许人工辅助但要说明方法"。
  - **引用命中率算法修正**：初版要求 chunk snippet 逐字含标注特征词，过严——语义召回的 chunk 未必逐字含标注词，但答案正确且有引用即应算命中。改为"答案正文含标注答案关键词 且 有引用"。
  - **评估前 DROP 向量索引重建**：测试 fixture 把索引重建成 8 维，生产 embedding 是 3072 维。评估脚本启动时先 `DROP INDEX ... IF EXISTS` 再用生产维度 `ensure_schema`，避免维度冲突。

- 踩了什么坑：
  - **run_chat 真实 bug**：探索代理发现 `run_chat` 把 `question`（字符串）直接传给 `search_chunks`（第二参数应是 embedding 向量），且 `Answer(question=question,...)` 塞了不存在的字段。B 板块测试用 mock run_chat，没跑真实链路，所以 bug 一直藏着。修复：run_chat 直接复用已验证正确的 `answer_question`，在各里程碑 emit 事件——彻底消除错误手写步骤的风险。
  - **向量索引维度冲突**：首次跑评估，向量查询报"Index query vector has 3072 dimensions, but indexed vectors have 8"。根因是测试把索引建成了 8 维。评估脚本启动时强制 DROP + 用生产维度重建。
  - **全量评估超时**：4 篇样本 × 逐 chunk LLM 抽取 + 问答，单次跑超 10 分钟。改后台跑 + 先单篇验证全链路。
  - **LLM 抽取随机性**：同一篇样本两次跑，实体召回率从 78.6% 降到 57.1%——LLM 每次抽的实体集合不同。这是真实情况，评估的价值正是量化这个波动。

## 2026-06-27 升级为 Agentic RAG（ReAct 检索-反思循环 + function calling）

- 做了什么：把问答核心从「固定线性 pipeline」升级为 **Agentic RAG**——LLM 自主决定检索什么、判断证据够不够、不够就换查询再检索。新增 `app/qa/agent.py`（ReAct 循环 + 两工具 + on_event 回调 + 降级信号），扩展 `app/clients/llm.py::chat_with_tools`，改造 `app/runs/tasks.py::run_chat` 调 agent 版并支持降级。复用现有检索组件，零新依赖。

- 这是什么：
  - **Agentic RAG（智能体化检索增强生成）**：传统 RAG 是「查一次库 → 拼 context → 生成」的一次性流水线；Agentic RAG 把「查什么、查几次、证据够不够」的决策权交给 LLM，让它像人查资料一样多轮检索、反思、补充。本项目的实现是 **ReAct（Reason + Act）**：模型在「思考调哪个工具」和「直接回答」之间循环。
  - **function calling（工具调用）**：OpenAI 协议的一个字段。你给 LLM 一份「工具清单」（每个工具有名字、参数 schema），LLM 决定要不要调、调哪个、传什么参数，返回结构化的 `tool_calls`；你执行后把结果塞回对话，LLM 再决策。相比让 LLM 自己输出「我要调用 xxx」的文本再正则解析，function calling 是协议级的、结构化的、可靠的。
  - **ReAct 循环**：`while 轮次 < 上限：模型决策 → 若返回 tool_calls 就执行并把结果回传、轮次+1 → 若无 tool_calls 则生成最终答案`。两条终止路径：模型主动停（证据够了）、或硬上限兜底（防死循环）。
  - **on_event 回调**：让 agent 循环把「现在在干嘛」通知外部（run_chat 用它 emit RunEvent），但 agent.py 本身不依赖 RunStore——这是「纯检索逻辑」和「进度广播」的解耦，agent 因此可独立单测。

- 为什么需要：线性 RAG「查一次就答」，遇到复杂问题（需要多角度检索、或证据分散在多个 chunk）会答不全、答不准。Agentic RAG 让模型自己判断「这次检索够不够」「要不要换个查询再试」「要不要挖一下实体关系」，检索质量天花板更高。这也是把项目从「RAG demo」推向「真正可用的 Agent」的关键一步，对简历展示价值大。

- 为什么这么做（关键取舍）：
  - **纯自研轻量循环 + 原生 function calling，不引 LangGraph/LangChain**：单 agent + 内部工具场景，自写 while 循环是主流共识，代码量小、可控、零新依赖，最大化保留编排控制权（符合 AGENTS.md「不被第三方框架牵着走」决策边界）。框架的价值在多 agent 编排、状态机、checkpointer，这些本项目都用不上，引入只会增加黑盒。
  - **工具粒度只做两个（vector_search + expand_entity）**：决策空间小、可控、token 省。rerank 不单独成工具（藏在 vector_search 内部），因为「搜完要不要重排」不该是模型决策点；额外的图谱路径查询 handoff 明确说「日后加」，现在加是超前设计。
  - **降级只在 LLM 不支持 tool calling 时触发**：区分「能力不支持」vs「单次工具失败」。前者（端点返回 BadRequestError）整个 agent 跑不了，回退线性 pipeline；后者（如某次 Neo4j 查询出错）不降级，而是把错误字符串回传给模型，让它自己决策（符合 handoff「工具失败不崩，回传错误让模型决策」）。
  - **证据池去重累积**：多轮检索的 chunk 用 `dict[chunk_id, ChunkHit]` 去重累积，保留完整 provenance，最终统一进 build_context 的 [n]↔Citation 闭环——引用可追溯红线不退化。
  - **token 裁剪**：工具结果只回 chunk_id + 正文前 200 字，不塞整段 chunk 反复留历史。messages 历史随轮次增长，但 max_turns=4 硬上限保证可控。
  - **检索用确定性 8 维向量（测试），LLM 决策与生成走真实调用**：test_agent 里 embed 用固定 8 维对齐测试 schema（避免真实 embedding 3072 维与测试 8 维 schema 冲突），但 `chat_with_tools`（决策）和 `chat`（生成）走真实 LLM——这才是要验证的 function calling 兼容性。

- 踩了什么坑：
  - **先实测再写代码**：动手写 agent 前先用一次性脚本验证 modelverse 端点（deepseek-v4-flash）是否支持 function calling——实测返回了合法的 `tool_calls`，确认可用后才动手。这是 handoff §五硬规则，避免写完才发现端点不支持、白费功夫。实测结果：端点完整支持 tools 字段。
  - **OpenAI tool_calls 必须全执行全回传**：协议允许一轮返回多个 tool_calls（并行调用），必须遍历执行每一个并把每个结果都以 `{"role":"tool","tool_call_id":对应id}` 回传，漏掉任何一个模型都会因找不到对应 tool result 而报错。
  - **assistant message 序列化要保留 tool_calls**：把 SDK 的 message 对象转成 dict 放回 messages 历史时，含 tool_calls 的情况必须保留 tool_calls 字段，否则下一轮模型上下文断裂。专门写了 `_assistant_msg_to_dict` 处理。
  - **test_tasks.py 旧断言被破坏**：原测试断言 run_chat 事件序列恒等于 `[SEARCHING,CHECKING,WRITING,IDLE]`，改成 agent 后必然破坏。按计划同步更新：降级路径守住这个序列，agentic 主路径测 `[SEARCHING,LINKING,WRITING,IDLE]`，两条线都覆盖。
  - **Docker 没起导致 test_agent 未端到端验证**：写完代码时 Docker Desktop 未启动，test_agent（需真 Neo4j）和其它集成测试一起正确 skip（非缺陷）。真 LLM function calling 兼容性已由手工脚本验证通过，但完整端到端（多轮检索 + 可追溯引用）待 Docker 起后补跑 `pytest tests/qa/test_agent.py`。

## 2026-06-28 PR 审计整改（B1-B15）

- 做了什么：按 PR 审计报告分三批整改 15 项（B1-B15）：补缺失依赖、加 API Key 鉴权 + CORS、LLM 超时防护、统一启动命令、BackgroundTasks 异步化、RunStore TTL、契约统一、embedding 维度校验、索引维度兜底、500 不泄密、RunEvent 可观测字段、LLM debug 日志、问答并发限流、PDF 页数上限。

- 这是什么：
  - **API Key 鉴权中间件**：在 FastAPI 请求进入路由前校验 `X-API-Key` header，不通过返 401。公开仓库防任何人 curl 删库/耗 token/读全图谱。
  - **asyncio.to_thread + call_soon_threadsafe**：把同步阻塞调用丢到线程池跑，让事件循环空闲处理 SSE 推送；工作线程内 emit 事件用 `call_soon_threadsafe` 投递回事件循环线程，保证 RunStore 单线程访问。
  - **向量索引维度兜底**：应用启动时校验索引维度与配置一致，不匹配（如测试残留）则 DROP+重建。

- 为什么需要：审计暴露了从"能跑"到"可公开可复现"的差距——缺失依赖让干净环境起不来、零鉴权让公开仓库裸奔、同步阻塞让 SSE 实时性失效、维度不匹配延迟暴露。这些是项目定位（公开 GitHub + 简历展示）的硬要求。

- 为什么这么做（关键取舍）：
  - **B5 异步化的跨线程难点**：run_chat 把 answer_question_agentic 整个包进 to_thread，agent 在工作线程内通过 on_event 回调 emit 事件。RunStore（dict/asyncio.Queue）非线程安全，工作线程不能直接调 store.append_event。用 `loop.call_soon_threadsafe(store.append_event, ...)` 把 emit 操作调度回事件循环线程——这是 Python 异步跨线程通信的标准做法。run_ingest/run_delete 的 emit 在 await 返回后（主循环线程）调用，无需特殊处理。
  - **B10 维度根治方案被 Neo4j 否决**：原计划用独立索引名（chunk_embedding_test）与生产物理隔离，实测 Neo4j 报 `IndexAlreadyExists: There already exists an index (:Chunk {embedding})`——**Neo4j 不允许同一 property 上建两个向量索引**。退而求其次：测试共用生产索引名，setup 重建为 TEST_DIM、teardown 恢复生产维度，再加应用 lifespan 启动时维度校验作兜底（测试强杀未恢复时，下次启动自动修正）。
  - **B2 鉴权默认空跳过**：API_KEY 为空时不校验，本地开发无感；部署时 .env 填值即启用。测试用 autouse fixture 显式置空，避免本地配了 key 时 TestClient 裸调 401。
  - **B14 限流只聚焦 run_chat**：问答是最耗 LLM 的链路（多轮 ReAct），Semaphore 限它即可；run_ingest/run_delete 单文档场景并发低，不限。

- 踩了什么坑：
  - **Neo4j 单 property 单向量索引限制**：B10 原方案（独立索引名隔离）实测不可行，CREATE VECTOR INDEX ... IF NOT EXISTS 把 IndexAlreadyExists 错误静默吞掉，表现为"建成功但 SHOW INDEXES 没有"。教训：对数据库特性的方案假设必须实测验证，不能只看 API 文档。
  - **asyncio.to_thread 必须 await**：第一版 `_run_chat_agentic` 写成 `return asyncio.to_thread(...)` 漏了 await，返回的是协程对象而非结果。to_thread 是协程函数，必须 await。
  - **test_agent 空证据测试用正交向量无效**：想用正交向量让召回为空，但 Neo4j 向量索引总会返回 top-k 最近邻（相似度低也返回）。改 mock search_chunks 返回空列表才是真正测空证据场景。
  - **B12 on_event 签名扩展破坏 lambda 测试**：on_event 从 `(stage, message)` 扩展为 `(stage, message, **extra)` 后，测试里的 `lambda s, m:` 报 unexpected keyword argument。加 `**extra` 适配。

## 2026-06-29 多轮对话记忆（会话存图谱 + 注入窗口）

- 做了什么：给问答补上多轮对话记忆。同会话连续追问，Agent 能利用近期历史上下文作答；历史以 Conversation/Message 节点存入 Neo4j，问答文本都向量化（建 message_embedding 索引）；提供会话 CRUD 接口。新增 `app/conversations/` 模块，扩展 schema（消息向量索引 + 约束），agent/pipeline 接收 history 参数，run_chat 串联会话读写，新增会话 CRUD 路由。

- 这是什么：
  - **多轮对话记忆**：之前每次问答是无状态的（POST /api/chat 只传 question），第二轮提问不"记得"第一轮。现在引入会话（Conversation）概念，同会话内的问答历史被存下来、注入到后续提问的上下文，Agent 能理解"它""那个"等指代。
  - **注入窗口（滚动窗口）**：历史不全量塞给 LLM（token 爆炸），只取最近 N 条（MAX_HISTORY_TURNS=6，约 3 组问答）注入 messages；全量仍存图谱不删。
  - **会话进图谱（B 方案）**：会话和消息作为 Neo4j 节点存储，而不是单独的关系库/文件。复用现有 Neo4j 基础设施，零新依赖，且消息向量化后未来可被向量召回（本次 Agent 工具暂不召回历史，schema 已铺路）。

- 为什么需要：单轮问答在追问场景下体验差（"它用什么数据库？"答不出"它"指什么）。多轮记忆是 RAG 从"单次检索"走向"连续对话"的关键一步，显著提升真实使用体验和简历展示价值。

- 为什么这么做（关键取舍）：
  - **历史注入而非向量召回**：用滚动窗口直接把近期历史塞进 messages，简单、可控、token 可预测；向量召回历史要额外一轮检索且相关性不保证。设计决策明确"本次不做召回，schema 已铺路留作后续"。
  - **会话存图谱而非内存/单独库**：复用 Neo4j，零新依赖；消息向量化建索引为未来"召回历史"铺路；与现有 Document/Chunk/Entity 同库，删除会话能级联清理。
  - **message_id 确定性 + 两段 Cypher**：message_id = `conv_id#turn_index`，但 turn_index 在 MERGE 时才确定——先单独算 next_turn，再用确定的 message_id MERGE，保证幂等可重试。
  - **conversation_id 同步解析**：首问时 chat 路由同步建会话拿 id，而非丢给异步任务——否则 HTTP 响应返回时任务没跑完，前端拿不到 id 无法追问。
  - **system prompt 守引用红线**：注入历史后，prompt 明确"回答仍须基于本次检索的【文档片段】并用 [n] 角标标注，不得仅凭历史记忆作答"，防止 Agent 凭记忆瞎答破坏引用可追溯。
  - **降级路径也带历史**：answer_question（线性降级版）也加 history 参数，保证 LLM 不支持 tool calling 时降级也能利用上下文。

- 踩了什么坑：
  - **Neo4j 5 的 size() 语法废弃**：`SET cv.message_count = size((cv)-[:HAS_MESSAGE]->(:Message))` 报 CypherSyntaxError，新版要用 `count { (cv)-[:HAS_MESSAGE]->(:Message) }`。Neo4j 5 的 Cypher 语法变化要注意。
  - **turn_index 必须在 Cypher 里 +1**：`_NEXT_TURN` 返回 `coalesce(max(turn_index),0)`，第一次调用返回 0，直接用作 turn_index 会让首条消息 turn_index=0（期望 1）。改为 `+ 1` 在 Cypher 内完成。
  - **message 索引可与 chunk 索引共存**：上一批 B10 发现"同 property 不能建两个向量索引"，但那是针对同 label+同 property。Message（:Message{embedding}）与 Chunk（:Chunk{embedding}）是不同 label，可以建两个独立索引——清单的索引隔离方案可行（B10 约束不适用）。
  - **ChatRequest 需配 alias**：前端契约用 camelCase（conversationId），Pydantic 默认不认，需 `Field(alias="conversationId")` + `populate_by_name=True`。
  - **Conversation/Message 无 document_id，清理需扩展**：现有 `_clean` fixture 按 document_id 前缀清理，会话节点没有该字段，必须加 `conversation_id STARTS WITH 'conv_test'` 清理，否则污染共享库。
  - **turn_index 自增与幂等的张力**：add_message 内部自增 turn_index，导致"连续两次 add 相同内容"会产生两条（turn_index 不同）。真正幂等靠 MERGE by message_id——当前 run_chat 是 BackgroundTask 失败不自动重试，重试场景不存在，幂等是防御性的。

## 2026-07-02 RunEvent 加 seq 序号（后注：「终态丢失」已澄清为非 bug）

> ✅ 2026-07-03 更正：当时以为的「长任务终态事件丢失」经实测澄清为**非 bug**——
> 实体抽取阶段本身耗时数分钟，终态事件最终会正常到达，此前是没等到任务结束就
> 误判丢失（详见 frontend/DEVLOG.md 同日更正 + tasks/lessons.md L8）。seq 字段
> 作为事件基础设施**保留**：Run 内事件有了序号，日后真做断线重连去重时可直接用。

- 做了什么：`RunEvent` 新增 `seq` 字段，由 `RunStore.append_event` 统一赋值
  （Run 内 1 起递增）；stream 与 `/events` 历史接口随 `model_dump` 自动输出。

- 这是什么：事件序号。前端 EventSource 断线重连后，后端 `subscribe` 会回放
  全部历史事件（防漏机制），代价是重连方会收到重复事件——seq 让前端能安全
  去重（只消费大于已见最大值的事件）。

- 为什么需要：修复「长任务终态丢失」bug 的后端配套。没有 seq，前端要么不敢
  放行自动重连（旧实现直接 close，卡死），要么重连后事件翻倍污染 UI。

- 为什么这么做：赋值收敛在 `append_event` 单点（而非各 emit 处手填），保证
  连续无洞；不用 SSE 协议层的 `id:`/`Last-Event-ID`（服务端还得实现按 id 跳过
  回放，复杂），客户端按 seq 过滤即可，符合简单优先。

## 2026-07-03 入库抽取阶段逐 chunk 发进度事件（on_progress 回调）

- 做了什么：`extract_document` / `extract_and_ingest` 新增可选 `on_progress(index, total)`
  回调，每个 chunk 开始抽取前触发；`run_ingest` 借此逐 chunk emit
  `EXTRACTING` 事件（「正在从分块 3/15 中抽取实体与关系…」）。顺带把
  阶段语义纠正：向量写入是 `INDEXING`、LLM 抽取是 `EXTRACTING`（此前两者
  标反了），事件序列变为 uploading→parsing→indexing→extracting(×N)→indexing→idle。

- 这是什么：长任务的细粒度进度上报。抽取阶段每 chunk 一次 LLM 调用，整段
  动辄数分钟；之前该阶段只发一条事件，前端全程停在同一句提示上，正是
  「SSE 终态丢失」误诊（见上一条）的错觉来源。

- 为什么需要：SSE 事件流的"活跃感"是用户判断任务没死的唯一依据。chunk 数
  是天然进度分母，逐 chunk 发一条 message 即可让前端持续看到推进，无需
  百分比协议或新字段。

- 为什么这么做：回调设计成纯 `Callable[[int, int], None]` 可选参数，extraction
  层不依赖 runs 层（保持分层）；跨线程 emit 沿用 run_chat 的既有模式——
  `extract_and_ingest` 跑在 `asyncio.to_thread` 工作线程里，RunStore 非线程
  安全，回调内用 `loop.call_soon_threadsafe` 把 append_event 投递回事件循环
  线程。备选方案是让 pipeline 直接持有 store/run_id，但那会让抽取层耦合
  运行时基础设施，回调更干净。

- 踩了什么坑：无。注意点是阶段顺序里 `INDEXING` 出现两次（向量写入在抽取
  之前，因 writer 的 MENTIONS 依赖 Chunk 节点已存在），mock 测试的期望
  序列要同步（tests/routers/test_documents.py）。

## 2026-07-03 抽取质量升级：prompt 重写 + 归并去 type + 图谱按度数排序

- 做了什么：一批围绕「实体召回率不达标 + 图谱噪声」的源头修正（交接单 B1–B6）。
  实体召回率从单篇基线 57.1% 提到全量 4 篇 87.7%（硬指标 ≥70%）。
  - **B1 抽取 prompt 重写**（`extraction/prompt.py`）：实体类型改封闭集合（模型
    不得自拟）、加排除清单（不抽代词/章节标题/泛化名词/整句）、加**枚举展开指令**
    （技术栈列举里每个具名技术单独成实体）、加中英混合 few-shot、英文术语保留原拼写。
  - **B2 归并 key 去 type**（`extraction/merge.py`）：合并键从 `(归一名, type)` 改为
    只按 `归一名`，type 取出现最多者（并列取先见）；`entity_id` 去掉 type 段。
  - **B3 mentionCount**（`extraction/writer.py`）：Entity 落 `mention_count`（本文档内
    提及次数），不做任何过滤。
  - **B4 图谱按度数排序**（`routers/graph.py`）：实体列表从按名改为按度数（MENTIONS
    入边 + RELATES 出入边）降序，响应加 `degree`/`mentionCount`。
  - **B6 问答输出格式**（`qa/prompt.py`）：提示补 Markdown 组织 + 角标紧跟句子。
  - **B5 评估扩容**（`evals/run_eval.py`）：报告加「抽出总数/标注数」与未匹配抽出
    实体（噪声候选）清单，让噪声可见。

- 这是什么：GraphRAG 的图谱质量约 60% 取决于抽取 prompt。召回不达标的主因是
  「技术栈一句话列举（Python / FastAPI / React + Vite + TypeScript…）被当成一个笼统
  实体」，漏掉里面每个具名技术——正是评估里漏抽的 React/Vite/TypeScript/Python 等。

- 为什么这么做（关键决策，均来自大脑交接单，不自行发挥）：
  - **不引抽取框架**：根因在 prompt 而非框架；自研链路是项目核心，保留项目级控制权。
  - **写入层不硬过滤**：曾想「单次提及且无关系的实体不入图」，否决——会直接拖低召回
    （标注实体可能只出现一次）。噪声降级交给展示层（B3 的 mentionCount + B4 的度数排序
    给前端分级用），源头只管「产出对 + 排序数据对」。
  - **归并去 type**：同名异型（React 被一处标「技术」、另一处「概念」）本会碎成两个
    节点。去 type 后按名归并、type 多数决，既并节点又不误伤召回（召回按归一名匹配，
    与 type 无关）。

- 指标前后对比（全量 4 篇，`evals/report.md`）：
  | 指标 | 基线(单篇) | 本次(4篇) | 目标 |
  |---|---|---|---|
  | 实体召回率 | 57.1% | **87.7%** | ≥70% ✅ |
  | 关系可用率 | 100% | 100% | ≥60% ✅ |
  | 引用命中率 | 100% | 89.6% | ≥70% ✅ |
  | 明显幻觉率 | 16.7% | 26.5% | ≤20% ⚠️ |

- 踩了什么坑 / 遗留给大脑：
  - **幻觉率 26.5% 超标是「假阳性」，非真幻觉**。B6 让答案变 Markdown 后，评估脚本
    的幻觉启发式（按 `[。.！!？?\n]+` 分句、统计无角标句）与之打架：① `Cytoscape.js`
    被句号切成 `Cytoscape`+`js**`，后半截无角标被计为幻觉；② Markdown 列表项的角标
    落在引导句上，单个 bullet 无角标也被计入。报告末尾 15 条「无引用论断」经核查 0 条
    是真编造。按大脑指示**不改幻觉算法**（避免为好看而改指标），如实记录，是否让评估
    分句器 Markdown 感知化留作后续任务由大脑定。
  - **图谱集成测试受共享库污染**：`test_list_entities` 原按 `LIMIT 100` 取，改度数降序后
    被真实入库的 323 个实体挤掉种子实体。改为 `limit=1000` + 断言「整表度数降序」，
    对任意数据都稳健。
  - LLM 偶发返回不合规 JSON（把技术栈列表吐成 `{'.gitignore': ...}` 字典）触发
    ValidationError，抽取管线 max_attempts=3 重试兜底，不中断整轮。

## 2026-07-12 公开解析器的内容策略元数据
- 做了什么：将文档块的内容类型、语言与抽取策略设为公开 parser 元数据，并在 `app.parsing` 导出对应枚举。
- 这是什么：`content_kind`/`language`/`extraction_policy` 是每个文档块的分类标签，下游抽取层可据此选择处理策略。
- 为什么需要：如果把判断逻辑写成按文件名的特例，不同类型内容无法共存于一个文档，也无法让下游扩展处理策略。
- 为什么这么做：让 parser 只识别并保存证据，不在解析阶段根据策略直接过滤文本，以保留原始偏移并允许下游灵活选择。
- 踩了什么坑：旧的公开包只导出 `Chunk` 等类型，隐藏的枚举让下游只能依赖字符串判断；通过公开 `ContentKind` 与 `ExtractionPolicy` 修复了这个契约缺口。
## 2026-07-12 抽取候选到写图的分阶段契约
- 做了什么：公开候选、证据、状态与校验接口，并把合并阶段的诊断信息带入 `ExtractionStats`。
- 这是什么：抽取先产生候选，再经证据和结构校验，只有 accepted 候选进入 merge，最后才由 writer 写入 Neo4j；review/rejected 原因保留在诊断列表中。
- 为什么需要：如果 LLM 的 JSON 直接写图，缺少来源或端点错误会变成不可追溯的图数据；分阶段可以阻挡无证据候选，同时让调用方看到被拒绝的原因。
- 为什么这么做：沿用现有 Pydantic 模型和 writer API，只新增默认为空的 `diagnostics` 字段与公共导出，旧的 `ExtractionStats` 构造方式仍然有效，避免破坏上层路由。
- 踩了什么坑：合并函数原本只接受可选的诊断列表，pipeline 没有传入它，导致拒绝的候选被日志记录后丢失；现在由 pipeline 建立列表并回传统计，Neo4j writer 测试仍需配置可用数据库才能运行。
## 2026-07-12 实体解析适配器：保留证据与安全回退
- 做了什么：新增纯内存 `ResolutionAdapter`，把 `MergedEntity` 转为 canonical groups、候选和诊断信息。
- 这是什么：适配器是连接抽取模型与后续写图层的边界，只整理数据，不直接调用 Neo4j；每个 group 保留来源实体、别名、mention chunk 和解析证据。
- 为什么需要：跨文档同名实体可以复用确定性解析结果，而未解析或有歧义的实体仍需可查询、可复核，不能因为一次合并判断丢掉原始实体 ID 和来源。
- 为什么这么做：先做 Unicode/大小写规范化，再让带来源的显式别名优先于普通 exact 身份，模糊结果只进入 review；这样人工纠错可以把已 bootstrap 的旧身份安全重指向目标，而 LLM 相似猜测仍不能自动合并。
- 踩了什么坑：没有 mention chunk 时不能伪造“已接受”的证据；适配器改为保留 document-scoped fallback ID，并将该项标为 unresolved，同时记录诊断。

## 2026-07-12 图谱查询：文档过滤与证据随边返回
- 做了什么：为实体列表、邻域和搜索接口增加可选 document 过滤，并让关系响应透传存储的 evidence chunk ID。
- 这是什么：local-first 查询先在限定文档和数量的局部范围内取图，再交给前端逐步展开；`evidenceChunkId` 是关系回到原文 Chunk 的指针，缺失时保持 `None`。
- 为什么需要：把整张图一次性加载会放大响应和渲染成本，也会让跨文档同名实体混在一起；过滤和证据指针让结果既可控又可复核。
- 为什么这么做：过滤条件作为 Cypher 参数传入而不是拼接字符串，沿用现有字段并只追加可选字段，兼容旧调用方，同时把边界限制留在查询层和 API 校验层。
- 踩了什么坑：Neo4j 真实集成测试依赖本地容器和 `.env`；fake-driver 测试可以验证参数传递与证据映射，但不能替代真实 Cypher 执行，提交前仍需在有 Neo4j 的环境复核。

## 2026-07-16 单文档抽取的有限并发
- 做了什么：将一个文档内的非 `SKIP` chunk 从逐条串行抽取改为最多 3 条并发，并让 pipeline 可用 `max_workers` 显式下调上限；完成后再发进度，最终按文档原始位置恢复成功和失败结果。
- 这是什么：`ThreadPoolExecutor` 是 Python 自带的有限线程池。这里每个线程只等待一次远程 LLM 请求，协调线程负责收集完成结果、记录可隔离失败和更新进度。
- 为什么需要：每个 chunk 的模型调用大部分时间花在网络等待上，串行执行会把等待时间逐段累加；有限并发能让这些等待重叠，同时避免一次提交过多请求。
- 为什么这么做：上限属于单次文档抽取，不是整个进程或模型服务商的全局限流；默认值直接放在函数参数中，不新增依赖或环境变量。合并层对“先见实体”有语义，因此不能按 future 完成顺序或 chunk ID 字符串排序，必须用原始列表位置恢复顺序。
- 踩了什么坑：非预期异常不能像 `ExtractionError` 一样跳过；协调线程会先退出线程池上下文、等待其他已提交任务正确收束，再把异常上抛。`SKIP` chunk 不提交线程池，也不计入进度总数。

## 2026-07-16 用规范实体覆盖层保留跨文档身份
- 做了什么：在文档级 `Entity` 之上新增 `CanonicalEntity` 与 accepted-only 的 `RESOLVES_TO`，把确定性 bootstrap、exact、带来源 alias、review/unresolved 状态接入抽取入库，并提供幂等 backfill 与删除孤儿节点的内部命令。
- 这是什么：规范实体覆盖层不是把原始实体物理合并，而是让每个带文档和 chunk 来源的源实体指向一个稳定的跨文档身份；原有 `MENTIONS`、`RELATES` 和问答链路仍保留在来源层。
- 为什么需要：同一个概念出现在多篇文档时，文档级 ID 会产生重复节点；直接合并又会破坏引用追溯和按文档删除。覆盖层同时保留了“它来自哪里”和“它与谁是同一个概念”。
- 为什么这么做：规范 ID 只对既有规范化名称做 SHA-256，实体类型不进入 ID，避免模型类型漂移改变身份；只有真实 `Chunk-[:MENTIONS]->Entity` 证据才能写 accepted 边，模糊匹配和冲突只保存待复核候选；别名必须先验证来源，不能用无出处的字符串映射。
- 踩了什么坑：一次消歧只能选择一个真实 mention 作为判断证据，不能把同一判断复制到所有 mention 上；重复运行时还要保留原 accepted 边的 method、reason 和 evidence，否则首轮 `bootstrap` 会在第二轮悄悄变成 `exact`。显式 alias 必须先于普通 exact，否则已 bootstrap 的旧拼写永远无法被人工重指。删除查询也不能由必需存在的 Document 驱动；各阶段要用 `OPTIONAL MATCH + collect/FOREACH` 保留一行，才能清掉 Document 已丢失但 Entity 仍残留的半成品状态。日常入库和单文档删除只能清理本次 source 原来指向的 canonical；全库孤儿清理只留给显式 backfill，否则测试或普通操作会顺带改动共享个人图谱。

## 2026-07-16 查询时规范投影与确定性主题社区
- 做了什么：新增显式 canonical communities、局部子图和搜索 API，在读取时把 accepted source `RELATES` 按规范端点与关系类型聚合，返回多文档证据、覆盖统计、有界 BFS 和支持度加权主题社区；旧 source API 与 QA 查询保持不变。
- 这是什么：查询时投影不是在 Neo4j 再存一套规范关系，而是用 `RESOLVES_TO` 临时把文档级关系映射成跨文档关系；单层 modularity local-moving 会比较“节点留在当前组”和“移动到相邻组”对社区内部连接强度的增益，因此能把只有弱桥相连的主题拆开，而不只是把整个连通分量称为一个社区。
- 为什么需要：直接展示 source graph 会把跨文档同义实体和 17 个 review 节点混在一起；只返回一条关系证据又会掩盖多文档支持。覆盖统计明确说明 accepted、review、排除关系和折叠自环的数量，`evidenceCount + evidenceTruncated` 则保证证据有界但不静默丢失。
- 为什么这么做：默认 `minConfidence=0.5` 与抽取 accepted floor 一致；关系只在两端 resolution 证据、关系 Chunk、同文档和双端 `MENTIONS` 都真实时参与聚合。边按完整有向键生成稳定 ID，社区按排序成员生成稳定 ID并以 canonical ID 打破增益平局；投影全程只读，所以别名改绑和文档删除会自动改变端点或支持数，不需要维护容易过期的规范 `RELATES`。
- 踩了什么坑：社区 API 的节点、边、证据和社区数量是四层不同边界，任何一层截断都必须显式标记；局部图还要优先保留 center，不能在探测到 `nodeLimit + 1` 后重新按 ID 排序把 center 截掉。真实测试使用独立临时 Neo4j 容器和 `test_wave3_*` 前缀，验证 alias 改绑、删除支持从 2→1→0、坏证据排除、source fingerprint 不变及 canonical `RELATES` 始终为 0，避免扫描或改写个人图库。

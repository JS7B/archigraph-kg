# A 板块规格：文档上传 / 入库 HTTP API

> 大脑窗口产出。后端工人窗口（feat/backend）照此实现，完成后 commit + 通知大脑评审。
> 开工前先 `git merge main` 同步（main 已领先 feat/backend）。

## 目标

把已完成的「解析 → embedding → 入图 → 抽取」链路用一个 HTTP 端点串起来，让前端（现在是 mock）能真正上传文档并触发完整入库。这是后续「Run 与事件流」板块的前置——上传动作将产生可观察的执行过程。

## 范围（做什么 / 不做什么）

**做：**
- 一个 HTTP 端点接收上传文件，落临时盘，跑完整入库链路，返回结果摘要。
- 端点同步执行（一次请求跑完整个链路后返回）。

**不做（明确划在范围外，避免板块膨胀）：**
- ❌ 异步任务队列（Celery/RQ）——「简单优先」决策边界，先用同步。等 Run 与事件流板块再考虑异步化。
- ❌ Run/RunEvent 记录——那是下一个板块。本板块只把链路串通。
- ❌ 进度推送（SSE/轮询）——同上，下个板块。
- ❌ 大文件分片上传、断点续传——超范围。
- ❌ 文档列表 / 删除 / 重建的 API——本板块只做「上传入库」一项。

## 端点设计

### `POST /api/documents`

- **Content-Type**: `multipart/form-data`
- **表单字段**:
  - `file`: 上传的文件（`.md` / `.txt` / `.pdf`）。单文件，一次请求一个。
- **处理流程**（按顺序，复用已有函数）：

```
1. 接收文件 → 校验扩展名（md/txt/pdf）→ 写入临时文件
2. parse_file(path, document_id)           # app.parsing.base.parse_file
   - document_id 用源文件名生成的稳定 id（沿用 parse_file 现有逻辑，别另造）
3. embed_chunks(doc.chunks)                # app.graph.embedding.embed_chunks
4. ingest_document(driver, doc, embeddings) # app.graph.writer.ingest_document
5. extract_and_ingest(driver, doc)         # app.extraction.pipeline.extract_and_ingest
6. 删除临时文件
7. 返回结果摘要（见下）
```

- **成功响应** `200`：
```json
{
  "documentId": "...",
  "documentName": "原始文件名",
  "chunkCount": 12,
  "extraction": {
    "entityCount": 8,
    "relationCount": 6,
    "mentionCount": 14,
    "failedChunks": 0
  }
}
```
（字段名沿用 `ExtractionStats` 已有属性，转 camelCase 输出，和 `/api/chat` 风格一致。）

- **错误响应**（沿用项目统一错误结构 `{error:{type,message}}`）：
  - `400` 不支持的文件类型
  - `413` 文件过大（设个上限，建议 10MB，走配置 `MAX_UPLOAD_MB`）
  - `500` 入库链路任一步失败（解析/embedding/写图/抽取）

## 实现要点（对接现状，避免踩坑）

1. **document_id 稳定性**：`parse_file` 内部已基于文件名生成 document_id。**不要**在路由里另造 id，否则和 chunk_id（`document_id#chunk_index`）对不上，破坏幂等。直接用 `parse_file(path)` 返回的 `doc.document_id`。
2. **embedding 维度**：`ingest_document` 会校验维度。`embed_chunks` 应已产出正确维度向量，但实现时确认 `EMBEDDING_DIM` 配置贯穿一致（schema → embed → ingest 三处维度必须同源）。
3. **幂等**：`ingest_document` 用确定性 chunk_id MERGE、`extract_and_ingest` 写入也是 MERGE 语义。同一文件重复上传**不应**产生重复数据——写一条测试覆盖这个场景。
4. **临时文件清理**：用 `try/finally` 或 `tempfile` 上下文管理器，确保链路成功或失败都删临时文件，不留在磁盘。
5. **driver 获取**：路由里用 `request.app.state.neo4j`（和 `/api/chat` 一致），别在路由里新建 driver。
6. **扫描版 PDF**：`parse_pdf` 已对扫描页 warning 降级、不报错——A 板块沿用，不额外处理。

## 配置项（新增）

在 `app/config.py` 的 Settings 加一项（走环境变量，不硬编码）：
- `MAX_UPLOAD_MB: int = 10` —— 上传大小上限。`.env.example` 同步补上这一行 + 注释。

## 路由挂载

在 `main.py` 的 `create_app` 里 `include_router(documents_router)`，和 chat/health 同级。新文件 `app/routers/documents.py`。

## 验收标准（测试要求，TDD）

按项目惯例，测试真连 Neo4j、真实链路（沿用现有测试夹具的 `test_` 前缀自清理模式）。

**必测场景：**
1. ✅ 上传一个 `.md` 文件 → 200，返回 chunkCount/entityCount 正数，documentId 稳定。
2. ✅ 上传一个 `.txt` 文件 → 200，同上。
3. ✅ 上传一个 `.pdf` 文件 → 200，同上（用 evals/ 或 samples/ 下的小 PDF fixture）。
4. ✅ **重复上传同一文件 → chunk/entity 不翻倍**（幂等硬要求，对应硬规则「图谱无重复」）。
5. ✅ 上传不支持的扩展名（如 `.docx`）→ 400。
6. ✅ 上传超大文件（构造超 MAX_UPLOAD_MB）→ 413。
7. ✅ 入库后用 `/api/chunks/{chunk_id}` 能反查到刚写入的 chunk（端到端贯通验证）。
8. ✅ 临时文件在请求结束后不存在（清理验证）。

**测试组织**：`backend/tests/routers/test_documents.py`。复用现有 conftest/夹具（Neo4j driver、test_ 清理），别另起。

## 装新依赖？

本板块**不新增 Python 依赖**——文件上传用 FastAPI 内置（`python-multipart` 已是 FastAPI 依赖）。
如果运行时报缺 `python-multipart`，先 `pip show python-multipart` 确认，**装前必须先问用户**（全局约定）。

## DEVLOG 要求

在 `backend/DEVLOG.md` 追加一条本板块学习记录，按 AGENTS.md 模板。建议覆盖：
- multipart 上传怎么工作（FastAPI 的 `UploadFile`）
- 为什么用同步而非异步队列（决策边界）
- 临时文件清理的 try/finally 模式
- 幂等测试为什么重要（chunk_id 确定性 MERGE）

## 完成后的交接

1. 本地 commit（信息写清「做了什么」，如 `feat(documents): 文档上传入库 HTTP API`）。
2. `git merge main` 同步（消除基线落后假象）。
3. 通知大脑窗口：分支名 `feat/backend`，让大脑读 diff 评审。
4. 大脑 review 通过后合并 + 更新 todo + 推送。

## 不确定的点（开工前问大脑，别自行决定）

- 文件大小上限取 10MB 是否合适？（大脑倾向：先 10MB，够样本用，走配置日后可调。如无异议按此。）
- 是否需要在上传端点同时触发 embedding 失败的重试？（大脑倾向：不需要。embedding 失败属于环境问题，应直接 500 报错让用户看到，不静默重试。）

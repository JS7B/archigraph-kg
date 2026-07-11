import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, ApiError, BASE_URL } from '../../api/client'
import { Button, Card, Chip, DataValue, Eyebrow, StatusBadge } from '../../components/ui'
import { useRunEvents } from '../../hooks/useRunEvents'
import type { DocumentMeta, DocumentSourceType, IndexStatus, ParseStatus, RunEvent, Stage } from '../../types'
import styles from './LibraryView.module.css'

const sourceTypeLabels: Record<DocumentSourceType, string> = {
  pdf: 'PDF',
  markdown: 'Markdown',
  txt: 'TXT',
  repo: '仓库',
}

const parseStatusLabels: Record<ParseStatus, string> = {
  pending: '待解析',
  parsing: '解析中',
  parsed: '已解析',
  failed: '解析失败',
}

const indexStatusLabels: Record<IndexStatus, string> = {
  pending: '待索引',
  indexing: '索引中',
  indexed: '已索引',
  failed: '索引失败',
}

const parseStatusTones: Record<ParseStatus, 'success' | 'error' | 'info' | 'neutral'> = {
  pending: 'neutral',
  parsing: 'info',
  parsed: 'success',
  failed: 'error',
}

const indexStatusTones: Record<IndexStatus, 'success' | 'error' | 'info' | 'neutral'> = {
  pending: 'neutral',
  indexing: 'info',
  indexed: 'success',
  failed: 'error',
}

interface IngestRunCreated {
  runId: string
  documentId: string
  documentName: string
}

interface DeleteRunCreated {
  runId: string
  documentId: string
}

// 入库/删除 Run 各 stage 的进度标签（中文）。抽取阶段的逐 chunk 进度细节由
// 事件 message 承载（如「正在从分块 3/15 中抽取实体与关系…」），此处只标阶段名。
const stageLabels: Record<Stage, string> = {
  idle: '已完成',
  uploading: '接收文件中',
  parsing: '解析文档中',
  extracting: '抽取实体关系中',
  linking: '连接关系中',
  indexing: '写入图谱中',
  searching: '检索中',
  checking: '校验中',
  writing: '生成中',
  deleting: '删除文档中',
  rebuilding: '重建索引中',
  error: '出错',
}

// 后端支持的扩展名（与 documents.py _SUPPORTED 对齐）。
const ACCEPTED_EXT = '.md,.txt,.pdf'

export function LibraryView() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  // 待确认删除的文档 id（非空时弹出确认框）
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const listRequestGeneration = useRef(0)
  const isBusy = activeRunId !== null

  const refresh = useCallback(async () => {
    const generation = ++listRequestGeneration.current
    try {
      const list = await apiFetch<DocumentMeta[]>('/api/documents')
      if (generation !== listRequestGeneration.current) return
      setDocuments(list)
      setLoadError(null)
    } catch (err) {
      if (generation !== listRequestGeneration.current) return
      const msg = err instanceof ApiError ? err.message : '请求失败，请确认后端已启动'
      setLoadError(msg)
    }
  }, [])

  useEffect(() => {
    const generation = ++listRequestGeneration.current
    apiFetch<DocumentMeta[]>('/api/documents')
      .then((list) => {
        if (generation !== listRequestGeneration.current) return
        setDocuments(list)
        setLoadError(null)
      })
      .catch((err: unknown) => {
        if (generation !== listRequestGeneration.current) return
        const msg = err instanceof ApiError ? err.message : '请求失败，请确认后端已启动'
        setLoadError(msg)
      })
    return () => {
      if (generation === listRequestGeneration.current) listRequestGeneration.current += 1
    }
  }, [])

  // 终态到达：刷新文档列表并结束 Run 订阅。
  const handleTerminal = useCallback((event: RunEvent) => {
    if (event.status === 'succeeded') {
      setActiveRunId(null)
      setRunError(null)
      void refresh()
    } else if (event.status === 'failed') {
      setActiveRunId(null)
      setRunError(event.message || '操作失败')
    }
  }, [refresh])

  const { events, currentStage } = useRunEvents(activeRunId, { onTerminal: handleTerminal })

  async function handleUpload(file: File) {
    // multipart 上传：必须用原生 fetch，apiFetch 会强制 JSON content-type。
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${BASE_URL}/api/documents`, { method: 'POST', body: form })
      if (!res.ok) {
        let msg = res.statusText
        try {
          const body = await res.json()
          if (body?.error?.message) msg = body.error.message
        } catch {
          /* 非 JSON 错误体，沿用 statusText */
        }
        setRunError(msg)
        return
      }
      const { runId } = (await res.json()) as IngestRunCreated
      setRunError(null)
      setActiveRunId(runId)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : '上传请求失败')
    }
  }

  // 删除文档：需带 ?confirm=true（后端安全设计）。调用前由弹窗二次确认。
  async function handleDelete(documentId: string) {
    try {
      const { runId } = await apiFetch<DeleteRunCreated>(
        `/api/documents/${encodeURIComponent(documentId)}?confirm=true`,
        { method: 'DELETE' },
      )
      setRunError(null)
      setActiveRunId(runId)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '删除请求失败'
      setRunError(msg)
    }
  }

  // 确认删除：调用 handleDelete 并关闭弹窗。
  function confirmDelete() {
    if (pendingDelete) {
      void handleDelete(pendingDelete)
      setPendingDelete(null)
    }
  }

  const summary = useMemo(
    () => ({
      documentCount: documents.length,
      chunkCount: documents.reduce((total, document) => total + document.chunkCount, 0),
    }),
    [documents],
  )

  const lastMessage = events[events.length - 1]?.message

  return (
    <section className={styles.library}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <div className={styles.titleBlock}>
            <Eyebrow>Knowledge Base</Eyebrow>
            <h1 className={styles.title}>文档库</h1>
          </div>
          <div className={styles.summary} aria-label="文档库统计">
            <DataValue label="文档">{summary.documentCount}</DataValue>
            <span className={styles.summaryText}>个文档</span>
            <DataValue label="chunks">{summary.chunkCount}</DataValue>
            <span className={styles.summaryText}>个可追溯片段</span>
          </div>
          {isBusy && (
            <div className={styles.summary} role="status" aria-live="polite">
              <Chip tone="accent">{stageLabels[currentStage]}</Chip>
              {lastMessage && <span className={styles.summaryText}>{lastMessage}</span>}
            </div>
          )}
          {runError && <div className={styles.runError}>{runError}</div>}
          {loadError && <div className={styles.runError}>加载失败：{loadError}</div>}
        </div>
        <div className={styles.actions}>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXT}
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void handleUpload(file)
              // 清空 value 允许重复选择同一文件触发 onChange。
              event.target.value = ''
            }}
          />
          <Button variant="primary" disabled={isBusy} onClick={() => fileInputRef.current?.click()}>
            上传文档
          </Button>
          <Button variant="ghost" onClick={() => void refresh()} aria-label="刷新文档列表">
            刷新列表
          </Button>
        </div>
      </header>

      {documents.length > 0 ? (
        <div className={styles.list} aria-label="文档列表">
          {documents.map((document) => (
            <Card key={document.id} className={styles.documentCard} interactive padding="lg">
              <div className={styles.cardHeader}>
                <div className={styles.documentNameGroup}>
                  <h2 className={styles.documentName}>{document.name}</h2>
                  <div className={styles.statusRow}>
                    <StatusBadge status={parseStatusTones[document.parseStatus]}>
                      {parseStatusLabels[document.parseStatus]}
                    </StatusBadge>
                    <StatusBadge status={indexStatusTones[document.indexStatus]}>
                      {indexStatusLabels[document.indexStatus]}
                    </StatusBadge>
                  </div>
                </div>
                <Chip className={styles.sourceChip} tone="accent">
                  {sourceTypeLabels[document.sourceType]}
                </Chip>
              </div>

              <div className={styles.metaRow}>
                <span className={styles.metaCopy}>
                  {document.chunkCount > 0 ? '已切分为引用片段' : '等待生成可引用 chunks'}
                </span>
                <DataValue label="chunks">{document.chunkCount}</DataValue>
              </div>

              <div className={styles.cardActions}>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={isBusy}
                  onClick={() => setPendingDelete(document.id)}
                >
                  删除
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className={styles.emptyState} padding="lg">
          <Eyebrow>Empty Library</Eyebrow>
          <h2 className={styles.emptyTitle}>还没有文档</h2>
          <p className={styles.emptyCopy}>上传一份文档，开始构建可追溯引用的个人知识库。</p>
          <Button variant="primary" disabled={isBusy} onClick={() => fileInputRef.current?.click()}>
            上传文档
          </Button>
        </Card>
      )}

      {/* 删除二次确认对话框（键盘可达：autoFocus 确认按钮） */}
      {pendingDelete && (
        <div className={styles.confirmOverlay} role="dialog" aria-modal="true" aria-label="确认删除文档">
          <div className={styles.confirmBox}>
            <p className={styles.confirmText}>确定删除这个文档？删除后无法恢复。</p>
            <div className={styles.confirmActions}>
              <Button variant="ghost" onClick={() => setPendingDelete(null)}>
                取消
              </Button>
              <Button variant="primary" onClick={confirmDelete} autoFocus>
                删除
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

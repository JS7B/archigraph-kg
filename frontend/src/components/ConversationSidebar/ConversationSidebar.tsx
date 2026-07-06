import { useState } from 'react'
import type { Conversation } from '../../types'
import { Button } from '../ui'
import styles from './ConversationSidebar.module.css'

interface ConversationSidebarProps {
  conversations: Conversation[]
  currentId: string | null
  loading?: boolean
  /** 切换到指定会话。 */
  onSelect: (id: string) => void
  /** 新建会话。 */
  onCreate: () => void
  /** 重命名会话（内部已做行内编辑与空标题过滤）。 */
  onRename: (id: string, title: string) => void
  /** 删除会话（内部已做二次确认）。 */
  onDelete: (id: string) => void
}

/**
 * 会话侧边栏：会话列表 + 新建 + 切换 + 重命名（行内编辑）+ 删除（带二次确认）。
 * 复用现有 UI 基件与 tokens，风格对齐 Linear/Notion 工程感。
 * 无障碍：会话项可键盘聚焦、:focus-visible 焦点环、aria-label；删除二次确认对话框可达。
 */
export function ConversationSidebar({
  conversations,
  currentId,
  loading = false,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: ConversationSidebarProps) {
  // 待确认删除的会话 id（非空时弹出确认框）。
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  // 行内编辑中的会话 id 与草稿标题（非空时该项标题替换为输入框）。
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  function confirmDelete() {
    if (pendingDelete) {
      onDelete(pendingDelete)
      setPendingDelete(null)
    }
  }

  function startEdit(c: Conversation) {
    setEditingId(c.conversationId)
    setDraft(c.title)
  }

  // 提交编辑：空白标题视为取消（保留原名）。
  function commitEdit() {
    if (editingId) {
      const title = draft.trim()
      if (title) onRename(editingId, title)
      setEditingId(null)
    }
  }

  return (
    <aside className={styles.sidebar} aria-label="会话列表">
      <div className={styles.header}>
        <h2 className={styles.title}>会话</h2>
        <Button variant="primary" onClick={onCreate} aria-label="新建会话">
          + 新建
        </Button>
      </div>

      {loading && <p className={styles.hint}>加载会话中…</p>}

      {!loading && conversations.length === 0 && (
        <p className={styles.hint}>还没有会话。点「新建」开始一次对话。</p>
      )}

      {!loading && conversations.length > 0 && (
        <ul className={styles.list}>
          {conversations.map((c) => {
            const isActive = c.conversationId === currentId
            return (
              <li key={c.conversationId}>
                <div
                  className={`${styles.item} ${isActive ? styles.itemActive : ''}`}
                  role="button"
                  tabIndex={0}
                  aria-current={isActive ? 'true' : undefined}
                  onClick={() => onSelect(c.conversationId)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelect(c.conversationId)
                    }
                  }}
                >
                  {editingId === c.conversationId ? (
                    <input
                      className={styles.editInput}
                      value={draft}
                      autoFocus
                      aria-label="会话标题"
                      onChange={(e) => setDraft(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={commitEdit}
                      onKeyDown={(e) => {
                        // 阻止冒泡到会话项的 Enter/空格选中；输入法选词回车不提交。
                        e.stopPropagation()
                        if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
                          e.preventDefault()
                          commitEdit()
                        } else if (e.key === 'Escape') {
                          setEditingId(null)
                        }
                      }}
                    />
                  ) : (
                    <span className={styles.itemTitle}>{c.title}</span>
                  )}
                  <span className={styles.itemMeta}>
                    {formatTime(c.createdAt)} · {c.messageCount} 条
                  </span>
                  <button
                    type="button"
                    className={styles.renameBtn}
                    aria-label={`重命名会话 ${c.title}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      startEdit(c)
                    }}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className={styles.delBtn}
                    aria-label={`删除会话 ${c.title}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      setPendingDelete(c.conversationId)
                    }}
                  >
                    ×
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {/* 删除二次确认对话框（键盘可达：Esc 取消、确认按钮可 Tab） */}
      {pendingDelete && (
        <div className={styles.confirmOverlay} role="dialog" aria-modal="true" aria-label="确认删除会话">
          <div className={styles.confirmBox}>
            <p className={styles.confirmText}>确定删除这个会话？删除后无法恢复。</p>
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
    </aside>
  )
}

function formatTime(ms: number): string {
  const d = new Date(ms)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) {
    return `今天 ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}

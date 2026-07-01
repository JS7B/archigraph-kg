import { useEffect, useRef, useState } from 'react'
import { TopBar, type ViewKey } from './components/TopBar/TopBar'
import { WorkbenchView } from './views/WorkbenchView/WorkbenchView'
import { LibraryView } from './views/LibraryView/LibraryView'
import { GraphView } from './views/GraphView/GraphView'
import { SettingsView } from './views/SettingsView/SettingsView'
import { StyleGallery } from './views/StyleGallery/StyleGallery'
import styles from './App.module.css'

// 设计系统预览：仅开发模式 + URL 带 ?preview 时挂载，不影响生产路由。
const showGallery =
  import.meta.env.DEV &&
  typeof window !== 'undefined' &&
  new URLSearchParams(window.location.search).has('preview')

export default function App() {
  const [view, setView] = useState<ViewKey>('workbench')
  const [settingsOpen, setSettingsOpen] = useState(false)
  // F6 焦点管理：打开时记下触发按钮，移焦到关闭按钮；关闭时还焦回去。
  const triggerRef = useRef<HTMLElement | null>(null)
  const closeBtnRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (settingsOpen) {
      triggerRef.current = document.activeElement as HTMLElement | null
      closeBtnRef.current?.focus()
    } else if (triggerRef.current) {
      triggerRef.current.focus()
      triggerRef.current = null
    }
  }, [settingsOpen])

  if (showGallery) {
    return <StyleGallery />
  }

  return (
    <div className={styles.app}>
      <TopBar
        active={view}
        onChange={setView}
        onToggleSettings={() => setSettingsOpen((v) => !v)}
      />
      <main className={styles.main}>
        {/* 任务3：三个视图常驻渲染，用 hidden 切换显隐而非条件渲染。
            组件不卸载，WorkbenchView 的会话/消息等 state 天然保留（切走再回来不丢）。 */}
        <div className={styles.viewPane} hidden={view !== 'workbench'}><WorkbenchView /></div>
        <div className={styles.viewPane} hidden={view !== 'library'}><LibraryView /></div>
        <div className={styles.viewPane} hidden={view !== 'graph'}><GraphView /></div>
      </main>
      {settingsOpen && (
        <div
          className={styles.settingsOverlay}
          onClick={() => setSettingsOpen(false)}
        >
          {/* 点遮罩背景关闭；点内容区（settingsPlaceholder 内部）不关 */}
          <div
            className={styles.settingsPlaceholder}
            onClick={(e) => e.stopPropagation()}
          >
            <SettingsView />
            <button ref={closeBtnRef} onClick={() => setSettingsOpen(false)}>关闭</button>
          </div>
        </div>
      )}
    </div>
  )
}

import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Button } from './components/ui'
import { TopBar, type ViewKey } from './components/TopBar/TopBar'
import { WorkbenchView } from './views/WorkbenchView/WorkbenchView'
import { LibraryView } from './views/LibraryView/LibraryView'
import { SettingsView } from './views/SettingsView/SettingsView'
import { StyleGallery } from './views/StyleGallery/StyleGallery'
import styles from './App.module.css'

const LazyGraphView = lazy(() =>
  import('./views/GraphView/GraphView').then((module) => ({ default: module.GraphView })),
)

// 设计系统预览：仅开发模式 + URL 带 ?preview 时挂载，不影响生产路由。
const showGallery =
  import.meta.env.DEV &&
  typeof window !== 'undefined' &&
  new URLSearchParams(window.location.search).has('preview')

export default function App() {
  const [view, setView] = useState<ViewKey>('workbench')
  const [graphActivated, setGraphActivated] = useState(false)
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
        onChange={(nextView) => {
          if (nextView === 'graph') setGraphActivated(true)
          setView(nextView)
        }}
        onToggleSettings={() => setSettingsOpen((v) => !v)}
      />
      <main className={styles.main}>
        {/* 任务3：三个视图常驻渲染，用 hidden 切换显隐而非条件渲染。
            组件不卸载，WorkbenchView 的会话/消息等 state 天然保留（切走再回来不丢）。 */}
        <div className={styles.viewPane} hidden={view !== 'workbench'}><WorkbenchView /></div>
        <div className={styles.viewPane} hidden={view !== 'library'}><LibraryView /></div>
        {graphActivated && (
          <Suspense
            fallback={<div className={styles.viewPane} role="status">正在加载图谱视图…</div>}
          >
            <div className={styles.viewPane} hidden={view !== 'graph'}><LazyGraphView /></div>
          </Suspense>
        )}
      </main>
      {settingsOpen && (
        <div
          className={styles.settingsOverlay}
          onClick={() => setSettingsOpen(false)}
        >
          {/* 点遮罩背景关闭；点内容区（settingsDrawer 内部）不关。
              关闭按钮放在抽屉顶部：打开时聚焦它，滚动位置自然停在开头
              （放底部会因 focus 自动滚到底，见 frontend/DEVLOG.md）。 */}
          <div
            className={styles.settingsDrawer}
            role="dialog"
            aria-modal="true"
            aria-label="设置"
            onClick={(e) => e.stopPropagation()}
          >
            <header className={styles.settingsHeader}>
              <h1 className={styles.settingsTitle}>设置</h1>
              <Button
                ref={closeBtnRef}
                size="sm"
                onClick={() => setSettingsOpen(false)}
              >
                关闭
              </Button>
            </header>
            <div className={styles.settingsBody}>
              <SettingsView />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { TopBar, type ViewKey } from './components/TopBar/TopBar'
import { WorkbenchView } from './views/WorkbenchView/WorkbenchView'
import { LibraryView } from './views/LibraryView/LibraryView'
import { GraphView } from './views/GraphView/GraphView'
import { SettingsView } from './views/SettingsView/SettingsView'
import styles from './App.module.css'

export default function App() {
  const [view, setView] = useState<ViewKey>('workbench')
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <div className={styles.app}>
      <TopBar
        active={view}
        onChange={setView}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className={styles.main}>
        {view === 'workbench' && <WorkbenchView />}
        {view === 'library' && <LibraryView />}
        {view === 'graph' && <GraphView />}
      </main>
      {settingsOpen && (
        <div className={styles.settingsPlaceholder}>
          <SettingsView />
          <button onClick={() => setSettingsOpen(false)}>关闭</button>
        </div>
      )}
    </div>
  )
}

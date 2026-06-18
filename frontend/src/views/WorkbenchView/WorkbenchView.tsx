import styles from './WorkbenchView.module.css'

export function WorkbenchView() {
  return (
    <div className={styles.workbench}>
      <section className={styles.mainCol}>
        <div className={styles.chatThread}>问答对话流（占位）</div>
        <div className={styles.citation}>引用证据区（占位）</div>
        <div className={styles.composer}>输入框（占位）</div>
      </section>
      <aside className={styles.sideCol}>
        <div className={styles.stageSlot}>像素 Agent 舞台（占位）</div>
        <div className={styles.timelineSlot}>运行事件时间线（占位）</div>
      </aside>
    </div>
  )
}

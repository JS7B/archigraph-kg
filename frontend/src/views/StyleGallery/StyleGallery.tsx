import { useState } from 'react'
import {
  Button,
  Card,
  Panel,
  Chip,
  StatusBadge,
  Eyebrow,
  DataValue,
} from '../../components/ui'
import { AgentRoom } from '../../components/AgentRoom/AgentRoom'
import { ALL_STAGES, sceneMap } from '../../components/AgentRoom/sceneMap'
import styles from './StyleGallery.module.css'

/**
 * 设计系统预览页（dev-only）。
 * 展示设计 token 与全部共享 UI 基件的变体，用于 P1 肉眼验收。
 * 仅在开发模式经 App 的 ?preview 入口挂载，不进入生产路由。
 */
export function StyleGallery() {
  const [clicks, setClicks] = useState(0)

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <Eyebrow>Design System · GraphRAG 工作台</Eyebrow>
        <h1 className={styles.title}>设计系统预览</h1>
        <p className={styles.lede}>
          冷调 slate 中性色、靛紫强调、等宽溯源数据。下面是设计 token 与全部共享基件的变体。
        </p>
      </header>

      {/* 调色板 */}
      <Section eyebrow="Foundation" title="调色板">
        <div className={styles.swatchGrid}>
          <Swatch name="bg" varName="--color-bg" />
          <Swatch name="surface" varName="--color-surface" />
          <Swatch name="surface-sunken" varName="--color-surface-sunken" />
          <Swatch name="border" varName="--color-border" />
          <Swatch name="border-strong" varName="--color-border-strong" />
          <Swatch name="accent" varName="--color-accent" dark />
          <Swatch name="accent-hover" varName="--color-accent-hover" dark />
          <Swatch name="accent-active" varName="--color-accent-active" dark />
          <Swatch name="accent-soft" varName="--color-accent-soft" />
          <Swatch name="text" varName="--color-text" dark />
          <Swatch name="text-body" varName="--color-text-body" dark />
          <Swatch name="text-muted" varName="--color-text-muted" dark />
          <Swatch name="text-subtle" varName="--color-text-subtle" dark />
          <Swatch name="success" varName="--color-success" dark />
          <Swatch name="warning" varName="--color-warning" dark />
          <Swatch name="error" varName="--color-error" dark />
          <Swatch name="info" varName="--color-info" dark />
        </div>
      </Section>

      {/* 字阶 */}
      <Section eyebrow="Foundation" title="字阶层级">
        <div className={styles.typeStack}>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-3xl)', fontWeight: 600, letterSpacing: 'var(--tracking-tight)' }}>
            3xl · 知识图谱问答 <span className={styles.typeMeta}>32 / semibold</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-2xl)', fontWeight: 600 }}>
            2xl · 视图主标题 <span className={styles.typeMeta}>25 / semibold</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-xl)', fontWeight: 600 }}>
            xl · 区块标题 <span className={styles.typeMeta}>20 / semibold</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>
            lg · 小标题 <span className={styles.typeMeta}>17 / semibold</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-md)' }}>
            md · 强调正文 <span className={styles.typeMeta}>15 / normal</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-base)' }}>
            base · 正文基准，知识库中每个 chunk 都保留来源与位置。<span className={styles.typeMeta}>14 / normal</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            sm · 次要说明文字 <span className={styles.typeMeta}>13 / muted</span>
          </p>
          <p className={styles.typeRow} style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-subtle)' }}>
            xs · 微标注 / 角标 <span className={styles.typeMeta}>12 / subtle</span>
          </p>
        </div>
      </Section>

      {/* Button */}
      <Section eyebrow="Primitive" title="Button">
        <div className={styles.row}>
          <Button variant="primary" onClick={() => setClicks((c) => c + 1)}>主操作</Button>
          <Button variant="secondary">次操作</Button>
          <Button variant="ghost">幽灵按钮</Button>
        </div>
        <div className={styles.row}>
          <Button variant="primary" size="sm">小号主操作</Button>
          <Button variant="secondary" size="sm">小号次操作</Button>
          <Button variant="primary" disabled>禁用态</Button>
        </div>
        <p className={styles.note}>主操作点击次数：<DataValue>{clicks}</DataValue></p>
      </Section>

      {/* Card */}
      <Section eyebrow="Primitive" title="Card">
        <div className={styles.cardRow}>
          <Card padding="md">
            <h3 className={styles.cardTitle}>静态卡片</h3>
            <p className={styles.cardText}>surface 表面 + 发丝边框 + 柔和阴影，padding=md。</p>
          </Card>
          <Card padding="md" interactive>
            <h3 className={styles.cardTitle}>可交互卡片</h3>
            <p className={styles.cardText}>悬浮时阴影抬升、边框加深、轻微上浮——把鼠标移上来看看。</p>
          </Card>
        </div>
      </Section>

      {/* Panel */}
      <Section eyebrow="Primitive" title="Panel（工作台分区容器）">
        <div className={styles.panelRow}>
          <Panel
            eyebrow="Workbench"
            title="运行事件"
            actions={<Button variant="ghost" size="sm">清空</Button>}
          >
            <ul className={styles.eventList}>
              <li><DataValue>parsing</DataValue> 拆分 paper.pdf …</li>
              <li><DataValue>extracting</DataValue> 已抽取 12 个实体</li>
              <li><DataValue>indexing</DataValue> 写入向量索引</li>
            </ul>
          </Panel>
          <Panel eyebrow="Sources" title="引用证据">
            <p className={styles.cardText}>带标题与 eyebrow 的分区容器，header 下有发丝分隔线，body 可滚动。</p>
          </Panel>
        </div>
      </Section>

      {/* Chip + StatusBadge */}
      <Section eyebrow="Primitive" title="Chip · StatusBadge">
        <div className={styles.row}>
          <Chip>neutral</Chip>
          <Chip tone="accent">accent</Chip>
          <Chip tone="accent">技术概念</Chip>
          <Chip>需求项</Chip>
        </div>
        <div className={styles.row}>
          <StatusBadge status="success">已索引</StatusBadge>
          <StatusBadge status="info">解析中</StatusBadge>
          <StatusBadge status="warning">待处理</StatusBadge>
          <StatusBadge status="error">失败</StatusBadge>
          <StatusBadge status="neutral">未开始</StatusBadge>
        </div>
      </Section>

      {/* DataValue — signature */}
      <Section eyebrow="Signature" title="DataValue（可溯源数据）">
        <p className={styles.cardText}>
          等宽字体承载可追溯的数据片段，呼应「引用可追溯」护城河：
        </p>
        <div className={styles.row}>
          <DataValue label="chunk">c_8f3a21</DataValue>
          <DataValue label="文档">attention-is-all-you-need.pdf</DataValue>
          <DataValue label="位置">p.4 §3.2</DataValue>
          <DataValue label="chunks">128</DataValue>
        </div>
      </Section>

      {/* AgentRoom — 12 状态全览 */}
      <Section eyebrow="Signature" title="像素档案员 · 12 状态">
        <p className={styles.cardText}>
          深紫调像素小房间：极简悬浮小人按状态横向飘到对应家具工位前，动作由家具自身运转
          （打印机吐纸 / 咖啡冒热气 / 档案柜开抽屉 / 碎纸机吞纸）表达。
          每个状态由真实 <code>RunEvent.stage</code> 驱动，下方网格展示全部 12 个状态。
        </p>
        <div className={styles.agentGrid}>
          {ALL_STAGES.map((s) => (
            <div key={s} className={styles.agentCell}>
              <AgentRoom stage={s} />
              <div className={styles.agentCap}>
                <DataValue>{s}</DataValue>
                <span className={styles.agentLabel}>{sceneMap[s].label}</span>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}

function Section({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHead}>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2 className={styles.sectionTitle}>{title}</h2>
      </div>
      <div className={styles.sectionBody}>{children}</div>
    </section>
  )
}

function Swatch({ name, varName, dark }: { name: string; varName: string; dark?: boolean }) {
  return (
    <div className={styles.swatch}>
      <div
        className={styles.swatchChip}
        style={{ background: `var(${varName})`, color: dark ? '#fff' : 'var(--color-text)' }}
      />
      <span className={styles.swatchName}>{name}</span>
    </div>
  )
}

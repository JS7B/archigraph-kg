import type { Stage } from '../../types'

/**
 * stage → 房间场景配置。
 * - label：状态标签（中文）。
 * - detail：进度文案（状态副标题）。
 * - busy：是否"工作中"（保留字段：驱动显示器明灭等家具环境动画；小人姿态改由
 *   data-action 驱动，见 useAgentPosition.ts / roomScenes.css）。
 *
 * Stage 枚举 12 个值锁定前端契约（types/runEvent.ts），不得改名（后端同源）。
 * 小人的行为剧本（走到哪个工位、做什么动作）由 behaviors.ts 定义。
 *
 * ⚠ 运行时可达性：AgentRoom 只挂在工作台（问答 Run），只会收到问答链路的
 *   idle / searching / checking / writing / linking / error 事件。文档处理各 stage
 *   （uploading / parsing / extracting / indexing / deleting / rebuilding）只在文档库
 *   订阅、从不到达 AgentRoom——下方这些条目**仅 StyleGallery 预览目录可见，运行时不可达**，
 *   保留是为让预览目录列全 12 状态，不代表 AgentRoom 会真的演出它们。
 */
export const sceneMap: Record<
  Stage,
  { label: string; detail: string; busy: 0 | 1 }
> = {
  idle: { label: '待命', detail: '空闲中', busy: 0 },
  uploading: { label: '搬运文档', detail: '接收文件', busy: 1 }, // 仅预览可达
  parsing: { label: '拆文件', detail: '解析文档', busy: 1 }, // 仅预览可达
  extracting: { label: '贴标签', detail: '抽取实体', busy: 1 }, // 仅预览可达
  linking: { label: '扩展图谱线索', detail: '扩展关系线索', busy: 1 },
  indexing: { label: '整理档案', detail: '写入图库', busy: 1 }, // 仅预览可达
  searching: { label: '翻找', detail: '向量召回', busy: 1 },
  checking: { label: '校对', detail: '校验引用', busy: 1 },
  writing: { label: '打字', detail: '生成回答', busy: 1 },
  deleting: { label: '碎纸', detail: '删除文档', busy: 1 }, // 仅预览可达
  rebuilding: { label: '重排', detail: '重建索引', busy: 1 }, // 仅预览可达
  error: { label: '出错', detail: '发生错误', busy: 0 },
}

// 12 个状态的固定顺序，供开发预览（StyleGallery）使用。
export const ALL_STAGES: Stage[] = [
  'idle', 'uploading', 'parsing', 'extracting', 'linking', 'indexing',
  'searching', 'checking', 'writing', 'deleting', 'rebuilding', 'error',
]

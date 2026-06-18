import type { Stage } from '../../types'

// stage → 动作配置。animClass 对应 animations.css 里的类名；
// scene 是工作间场景元素描述（占位阶段用文字标识，便于后续替换为像素道具）。
export const stageMap: Record<
  Stage,
  { label: string; animClass: string; scene: string }
> = {
  idle: { label: '待命', animClass: 'anim-idle', scene: '安静的工作间' },
  uploading: { label: '搬运文档', animClass: 'anim-uploading', scene: '门口收件筐' },
  parsing: { label: '拆文件', animClass: 'anim-parsing', scene: '拆包台' },
  extracting: { label: '贴实体标签', animClass: 'anim-extracting', scene: '标签贴纸' },
  linking: { label: '拉关系线', animClass: 'anim-linking', scene: '连线板' },
  indexing: { label: '整理档案柜', animClass: 'anim-indexing', scene: '档案柜抽屉' },
  searching: { label: '翻找文件', animClass: 'anim-searching', scene: '文件堆' },
  checking: { label: '校对引用', animClass: 'anim-checking', scene: '放大镜' },
  writing: { label: '打字输出', animClass: 'anim-writing', scene: '打字机' },
  deleting: { label: '碎纸', animClass: 'anim-deleting', scene: '碎纸机' },
  rebuilding: { label: '复印重排', animClass: 'anim-rebuilding', scene: '复印机' },
  error: { label: '查看错误', animClass: 'anim-error', scene: '红色纸条' },
}

// 12 个状态的固定顺序，供开发预览切换器使用。
export const ALL_STAGES: Stage[] = [
  'idle', 'uploading', 'parsing', 'extracting', 'linking', 'indexing',
  'searching', 'checking', 'writing', 'deleting', 'rebuilding', 'error',
]

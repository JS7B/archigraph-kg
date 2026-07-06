/**
 * 像素小人 · box-shadow 像素法 + 编译器
 *
 * 原理：把 8×8 网格图案（易读的字符串数组）编译成一串 box-shadow 坐标，
 * 渲染时用 1 个 div + 多层 box-shadow 画全部色块。
 *
 * 为什么这么做（折中）：
 * - 纯 box-shadow 像素法性能好（1 个 div），但手写坐标极难维护。
 * - 用 pattern 数组做单一数据源：改图案/配色只改下面的 PATTERN/COLOR（易读），
 *   box-shadow 字符串由 compile() 自动生成（运行一次，结果存常量）。
 *
 * 配色取向（v3 场景叙事版）：小人不是主体，工作台才是；但小人作为深紫房间里的
 * 视觉锚点，用多彩配色（橙卫衣 + 粉高光）让它跳出来，不沉闷、不与主区撞色。
 * 小人本体只悬浮，不做手臂逐帧——动作由横向飘移到家具工位 + 家具自身运转表达。
 */

// 配色（多彩活泼，对齐 tokens.css 的 --dude-* 变量）。
// 字符 → CSS 色：改色改 tokens.css，这里只映射到变量。
const COLOR: Record<string, string> = {
  h: 'var(--dude-hair)',  // 头发（紫）
  s: 'var(--dude-skin)',  // 肤色
  e: 'var(--dude-eye)',   // 眼睛/瞳
  g: 'var(--dude-glass)', // 眼镜框（档案员辨识特征）
  b: 'var(--dude-body)',  // 卫衣主色（橙，焦点色）
  B: 'var(--dude-body-hi)', // 卫衣高光（粉，右侧受光强侧）
  d: 'var(--dude-body-lo)', // 卫衣暗面（左侧受光弱侧）
  l: 'var(--dude-leg)',   // 腿
}

// 8列×8行 像素图案。字符：. 透明 | 其余见 COLOR。
// 第4行 .geseg.. —— g 眼镜框与 e 眼睛形成更明确的五官。
// 常态不在底稿里固化嘴型，避免 doze 状态覆盖层叠加出双重表情。
const PATTERN: string[] = [
  '..hhh...',
  '.hhhhh..',
  '.hssss..', // 额发 + 脸
  '.geseg..', // 眼镜框 + 眼
  '.sssss..', // 脸下半
  '..dbBBb.', // 卫衣（左 d 暗面 / 右 B 高光，三段受光造体积）
  '..dbbbb.',
  '..ll.ll.', // 腿（悬浮，短腿）
]

// 每格像素尺寸：宽 3 × 高 3 → 整体约 24×24。
export const DUDE_W = 24
export const DUDE_H = 24
const GRID_W = 3
const GRID_H = 3

/**
 * 把 pattern 编译成 box-shadow 字符串。
 * 每个非透明格变成一个 "{x}px {y}px 0 0 {color}" 投影（spread 0、模糊 0 = 硬边像素）。
 */
function compile(pattern: string[], color: Record<string, string>, gw: number, gh: number): string {
  const shadows: string[] = []
  pattern.forEach((row, y) => {
    const rowChars = row.split('')
    for (let x = 0; x < rowChars.length; x++) {
      const ch = rowChars[x]
      const c = color[ch]
      if (!c) continue
      shadows.push(`${(x * gw).toFixed(2)}px ${(y * gh).toFixed(2)}px 0 0 ${c}`)
    }
  })
  return shadows.join(', ')
}

// 编译结果（模块级常量，启动时算一次，渲染时直接用）。
export const DUDE_SHADOW = compile(PATTERN, COLOR, GRID_W, GRID_H)

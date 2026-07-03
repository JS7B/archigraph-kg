/**
 * remark 插件：把正文里的引用角标 `[n]` 转成链接节点 `[n](#cite-n)`，
 * 供 react-markdown 的 a 组件覆写渲染成内联引用芯片。
 *
 * 为什么用 AST 插件而非字符串正则预处理：
 *   字符串层全局替换会污染**代码区**——行内代码 `arr[0]` 与围栏代码块里的
 *   数字方括号会被替成 `[[0]](#cite-0)` 原样显示。本产品常答技术问题、代码频出。
 *   在 mdast 上只改写 `text` 节点即可天然跳过代码：代码是独立的 `inlineCode`/`code`
 *   节点（非 `text`、无 children），遍历时不会被碰到。
 *
 * 不引第三方遍历依赖，手写递归即可（结构简单）。
 */

// mdast 节点最小结构（只用到用得着的字段，避免引 @types/mdast）。
interface MdNode {
  type: string
  value?: string
  url?: string
  children?: MdNode[]
}

const CITE_MARKER = /\[(\d+)\]/g

// 把一个 text 节点按 [n] 切成 text/link 交替的节点序列（无 [n] 则原样返回）。
function splitTextNode(node: MdNode): MdNode[] {
  const value = node.value ?? ''
  const out: MdNode[] = []
  let last = 0
  let match: RegExpExecArray | null
  CITE_MARKER.lastIndex = 0
  while ((match = CITE_MARKER.exec(value)) !== null) {
    if (match.index > last) {
      out.push({ type: 'text', value: value.slice(last, match.index) })
    }
    out.push({
      type: 'link',
      url: `#cite-${match[1]}`,
      children: [{ type: 'text', value: match[0] }],
    })
    last = match.index + match[0].length
  }
  if (out.length === 0) return [node] // 无角标，保持原节点引用
  if (last < value.length) out.push({ type: 'text', value: value.slice(last) })
  return out
}

// 递归改写：容器节点的 text 子节点做切分；不进入已有 link（避免链接内套链接）。
function transform(node: MdNode): void {
  if (!node.children || node.type === 'link') return
  const next: MdNode[] = []
  for (const child of node.children) {
    if (child.type === 'text') {
      next.push(...splitTextNode(child))
    } else {
      transform(child)
      next.push(child)
    }
  }
  node.children = next
}

export function remarkCitations() {
  // 参数用 unknown 收口，避免 MdNode 与 unist Node 的函数逆变类型摩擦（内部再窄化）。
  return (tree: unknown): void => {
    transform(tree as MdNode)
  }
}

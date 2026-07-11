import { describe, expect, it } from 'vitest'
import { remarkCitations } from './remarkCitations'

describe('remarkCitations', () => {
  it('converts citation markers without changing inline or fenced code', () => {
    const tree = {
      type: 'root',
      children: [
        { type: 'paragraph', children: [{ type: 'text', value: '结论 [1]' }] },
        { type: 'paragraph', children: [{ type: 'inlineCode', value: 'arr[0]' }] },
        { type: 'code', value: 'const item = arr[2]' },
      ],
    }

    remarkCitations()(tree)

    expect(tree.children[0].children).toEqual([
      { type: 'text', value: '结论 ' },
      { type: 'link', url: '#cite-1', children: [{ type: 'text', value: '[1]' }] },
    ])
    expect(tree.children[1]).toEqual({
      type: 'paragraph',
      children: [{ type: 'inlineCode', value: 'arr[0]' }],
    })
    expect(tree.children[2]).toEqual({ type: 'code', value: 'const item = arr[2]' })
  })
})

import type { GraphNode } from '../../types'

function classToken(value: string | null | undefined, fallback: string): string {
  const normalized = value?.trim().toLocaleLowerCase().replace(/[^a-z0-9_-]+/g, '-')
  return normalized || fallback
}

function paletteIndex(value: string | null | undefined): number {
  const token = classToken(value, 'local')
  return [...token].reduce((sum, character) => sum + character.charCodeAt(0), 0) % 4
}

export function nodeVisualClasses(node: GraphNode, fallbackCommunity = 'local'): string {
  return [
    `type-${classToken(node.entityType, 'unknown')}`,
    `community-${classToken(node.communityId, fallbackCommunity)}`,
    `community-palette-${paletteIndex(node.communityId ?? fallbackCommunity)}`,
  ].join(' ')
}

export function edgeConfidenceClass(confidence: number | null | undefined): string {
  if (typeof confidence !== 'number' || !Number.isFinite(confidence)) return 'confidence-unknown'
  if (confidence >= 0.8) return 'confidence-high'
  if (confidence >= 0.5) return 'confidence-medium'
  return 'confidence-low'
}

export function fallbackPosition(id: string, index: number): { x: number; y: number } {
  let hash = 0
  for (const character of id) hash = (hash * 31 + character.charCodeAt(0)) | 0
  const angle = ((Math.abs(hash) % 360) * Math.PI) / 180
  const radius = 120 + (index % 4) * 45
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }
}

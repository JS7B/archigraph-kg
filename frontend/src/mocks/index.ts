import type { ChatMessage, RunEvent, DocumentMeta, GraphData } from '../types'

/**
 * 本地 mock 数据，严格对齐 src/types。
 * 仅用于静态界面演示（StyleGallery 等）与离线开发兜底；写操作（上传/删除/问答）
 * 已直连真实后端（见各 View）。内容围绕一篇技术论文 + 一个仓库文档 + 一份需求文档。
 */

// 对话流：用户提问 + Agent 带引用的回答
export const mockMessages: ChatMessage[] = [
  {
    id: 'm1',
    role: 'user',
    text: 'Transformer 为什么不用循环结构？自注意力解决了什么问题？',
  },
  {
    id: 'm2',
    role: 'agent',
    text: 'Transformer 完全用自注意力替代循环，主要解决两个问题：一是 RNN 必须按序列逐步计算、无法并行，训练慢；二是长距离依赖在循环结构里要经过很多步才能传递，容易衰减。自注意力让任意两个位置直接交互，路径长度恒为 O(1)，因此既能并行、又能更好地建模长程依赖。',
    answer: {
      text: 'Transformer 完全用自注意力替代循环，主要解决两个问题：一是 RNN 必须按序列逐步计算、无法并行，训练慢；二是长距离依赖在循环结构里要经过很多步才能传递，容易衰减。自注意力让任意两个位置直接交互，路径长度恒为 O(1)，因此既能并行、又能更好地建模长程依赖。',
      confidence: 'high',
      citations: [
        {
          index: 1,
          chunkId: 'c_8f3a21',
          documentId: 'attention-is-all-you-need.pdf',
          location: 'p.2 §1',
          snippet:
            'Recurrent models typically factor computation along the symbol positions of the input and output sequences ... precludes parallelization within training examples.',
        },
        {
          index: 2,
          chunkId: 'c_4d9b07',
          documentId: 'attention-is-all-you-need.pdf',
          location: 'p.6 §4',
          snippet:
            'Self-attention layers connect all positions with a constant number of sequentially executed operations, whereas a recurrent layer requires O(n) sequential operations.',
        },
      ],
    },
  },
  {
    id: 'm3',
    role: 'user',
    text: '多头注意力相比单头有什么好处？',
  },
  {
    id: 'm4',
    role: 'agent',
    text: '多头注意力把表示拆到多个子空间并行做注意力，让模型在不同位置同时关注来自不同表示子空间的信息，而单头会因为平均而削弱这种能力。',
    answer: {
      text: '多头注意力把表示拆到多个子空间并行做注意力，让模型在不同位置同时关注来自不同表示子空间的信息，而单头会因为平均而削弱这种能力。',
      confidence: 'medium',
      citations: [
        {
          index: 1,
          chunkId: 'c_1a77ce',
          documentId: 'attention-is-all-you-need.pdf',
          location: 'p.5 §3.2.2',
          snippet:
            'Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions.',
        },
      ],
    },
  },
]

// 运行事件流：一次问答 Run 的阶段轨迹（searching → checking → writing → succeeded）。
// 字段严格对齐后端契约：status 用 running/succeeded/failed，timestampMs camelCase，answer 终态才有。
export const mockRunEvents: RunEvent[] = [
  { stage: 'searching', status: 'running', message: '向量召回相关 chunk', answer: null, timestampMs: 1_718_600_000_000 },
  { stage: 'checking', status: 'running', message: '校对引用与证据', answer: null, timestampMs: 1_718_600_001_200 },
  { stage: 'writing', status: 'running', message: '生成带引用回答', answer: null, timestampMs: 1_718_600_002_400 },
  { stage: 'idle', status: 'succeeded', message: '回答完成，附 2 条引用', answer: null, timestampMs: 1_718_600_003_600 },
]

// 文档库：三类样本文档，覆盖不同解析/索引状态
export const mockDocuments: DocumentMeta[] = [
  {
    id: 'd1',
    name: 'attention-is-all-you-need.pdf',
    sourceType: 'pdf',
    parseStatus: 'parsed',
    indexStatus: 'indexed',
    chunkCount: 128,
  },
  {
    id: 'd2',
    name: 'langchain/README.md',
    sourceType: 'repo',
    parseStatus: 'parsed',
    indexStatus: 'indexing',
    chunkCount: 64,
  },
  {
    id: 'd3',
    name: '产品需求文档-知识库助手.md',
    sourceType: 'markdown',
    parseStatus: 'parsed',
    indexStatus: 'indexed',
    chunkCount: 42,
  },
  {
    id: 'd4',
    name: 'rag-survey-2024.pdf',
    sourceType: 'pdf',
    parseStatus: 'parsing',
    indexStatus: 'pending',
    chunkCount: 0,
  },
  {
    id: 'd5',
    name: 'notes.txt',
    sourceType: 'txt',
    parseStatus: 'failed',
    indexStatus: 'pending',
    chunkCount: 0,
  },
]

// 图谱：围绕 Transformer 的小型实体-关系图
export const mockGraph: GraphData = {
  nodes: [
    { id: 'e_transformer', label: 'Transformer', entityType: '技术概念' },
    { id: 'e_self_attn', label: 'Self-Attention', entityType: '技术概念' },
    { id: 'e_multihead', label: 'Multi-Head Attention', entityType: '技术概念' },
    { id: 'e_rnn', label: 'RNN', entityType: '技术概念' },
    { id: 'e_encoder', label: 'Encoder', entityType: '产品模块' },
    { id: 'e_decoder', label: 'Decoder', entityType: '产品模块' },
    { id: 'e_paper', label: 'Attention Is All You Need', entityType: '文献' },
    { id: 'e_google', label: 'Google Brain', entityType: '机构' },
  ],
  edges: [
    { id: 'r1', source: 'e_transformer', target: 'e_self_attn', relationType: '使用' },
    { id: 'r2', source: 'e_transformer', target: 'e_rnn', relationType: '替代' },
    { id: 'r3', source: 'e_self_attn', target: 'e_multihead', relationType: '组成' },
    { id: 'r4', source: 'e_transformer', target: 'e_encoder', relationType: '包含' },
    { id: 'r5', source: 'e_transformer', target: 'e_decoder', relationType: '包含' },
    { id: 'r6', source: 'e_paper', target: 'e_transformer', relationType: '提出' },
    { id: 'r7', source: 'e_google', target: 'e_paper', relationType: '发表' },
    { id: 'r8', source: 'e_encoder', target: 'e_self_attn', relationType: '使用' },
    { id: 'r9', source: 'e_decoder', target: 'e_multihead', relationType: '使用' },
  ],
}

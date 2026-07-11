import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'

const graphLifecycle = vi.hoisted(() => ({ moduleLoads: 0, mounts: 0, unmounts: 0 }))

vi.mock('./api/health', () => ({
  fetchHealthDeps: vi.fn().mockResolvedValue({ neo4j: 'ok', llm: 'configured' }),
}))

vi.mock('./views/WorkbenchView/WorkbenchView', () => ({
  WorkbenchView: () => <div>Workbench workspace</div>,
}))

vi.mock('./views/LibraryView/LibraryView', () => ({
  LibraryView: () => <div>Library workspace</div>,
}))

vi.mock('./views/GraphView/GraphView', async () => {
  const { useEffect } = await import('react')
  graphLifecycle.moduleLoads += 1
  return {
    GraphView: () => {
      useEffect(() => {
        graphLifecycle.mounts += 1
        return () => {
          graphLifecycle.unmounts += 1
        }
      }, [])
      return <div>Graph workspace</div>
    },
  }
})

vi.mock('./views/SettingsView/SettingsView', () => ({
  SettingsView: () => null,
}))

vi.mock('./views/StyleGallery/StyleGallery', () => ({
  StyleGallery: () => null,
}))

afterEach(cleanup)

it('loads GraphView on first graph navigation and keeps it mounted', async () => {
  render(<App />)

  expect(graphLifecycle.moduleLoads).toBe(0)
  expect(screen.queryByText('Graph workspace')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '图谱' }))
  const graph = await screen.findByText('Graph workspace')
  expect(graphLifecycle.moduleLoads).toBe(1)
  expect(graphLifecycle.mounts).toBe(1)

  fireEvent.click(screen.getByRole('button', { name: '问答' }))
  await waitFor(() => expect(graph).not.toBeVisible())
  expect(graphLifecycle.unmounts).toBe(0)
})

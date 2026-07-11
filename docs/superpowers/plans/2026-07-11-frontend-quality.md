# Frontend Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make frontend lint/test/build gates executable, move terminal Run handling to the SSE callback boundary, and load Cytoscape only after the graph view is first opened.

**Architecture:** Keep API calls and RunEvent as the single source of truth. Extend `useRunEvents` with a stable terminal callback, remove state-changing terminal effects from consumers, then add a lazy graph activation flag that preserves GraphView state after first load.

**Tech Stack:** React 19, TypeScript 6, Vite 8, ESLint 10, Vitest, Testing Library, jsdom.

## Global Constraints

- Work only on branch `feat/frontend-quality` in `D:\AgenX\archigraph-kg-frontend-quality`.
- Do not change backend APIs, RunEvent names, visual design, or citation semantics.
- Do not disable `react-hooks/set-state-in-effect` globally or raise the Vite chunk warning limit.
- Add only `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, and `jsdom`.
- Update `frontend/DEVLOG.md`; do not edit `tasks/todo.md` or merge to main.

---

### Task 1: Establish the frontend test and lint commands

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`

**Interfaces:**
- Produces: `npm run lint`, `npm run test`, and `npm run test:run`.
- Produces: jsdom tests with jest-dom matchers.

- [ ] **Step 1: Install the authorized dependencies**

Run:

```powershell
cd frontend
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom
```

Expected: `package.json` and `package-lock.json` record all four packages.

- [ ] **Step 2: Add exact scripts**

Set the scripts object to include:

```json
{
  "lint": "eslint .",
  "test": "vitest",
  "test:run": "vitest run"
}
```

- [ ] **Step 3: Add the Vitest configuration**

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    restoreMocks: true,
  },
})
```

Create `frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 4: Verify the harness**

Run: `npm run test:run -- --passWithNoTests`

Expected: exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src/test/setup.ts
git commit -m "test(frontend): add vitest quality commands"
```

### Task 2: Add terminal-event coverage to useRunEvents

**Files:**
- Create: `frontend/src/hooks/useRunEvents.test.tsx`
- Modify: `frontend/src/hooks/useRunEvents.ts`

**Interfaces:**
- Produces: `UseRunEventsOptions` with optional `onTerminal(event: RunEvent): void`.
- Preserves: `{ events, currentStage, error }` return shape.

- [ ] **Step 1: Write failing hook tests**

Mock `subscribeRunEvents`, capture its `onEvent` callback, and assert these cases:

```ts
it('clears old events when runId changes', () => {
  // emit one running event for run-a, rerender with run-b, expect [] and idle
})

it('delivers one terminal callback per run', () => {
  // emit the same succeeded event twice, expect onTerminal once
})
```

Use `renderHook`, `act`, and `rerender` from `@testing-library/react`.

- [ ] **Step 2: Prove the tests fail**

Run: `npm run test:run -- src/hooks/useRunEvents.test.tsx`

Expected: failure because `onTerminal` is not supported.

- [ ] **Step 3: Implement the stable callback boundary**

Add:

```ts
export interface UseRunEventsOptions {
  onTerminal?: (event: RunEvent) => void
}

const TERMINAL = new Set(['succeeded', 'failed'])
```

Keep the latest callback in a ref, reset a handled-terminal ref when `runId` changes, and invoke `onTerminal` from the `subscribeRunEvents` event callback only for the first terminal event of that run.

- [ ] **Step 4: Verify**

Run: `npm run test:run -- src/hooks/useRunEvents.test.tsx`

Expected: all hook tests pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/hooks/useRunEvents.ts frontend/src/hooks/useRunEvents.test.tsx
git commit -m "refactor(frontend): expose terminal run callback"
```

### Task 3: Remove state-changing effects from the four views

**Files:**
- Modify: `frontend/src/views/WorkbenchView/WorkbenchView.tsx`
- Modify: `frontend/src/views/LibraryView/LibraryView.tsx`
- Modify: `frontend/src/views/GraphView/GraphView.tsx`
- Modify: `frontend/src/views/SettingsView/SettingsView.tsx`
- Create: `frontend/src/views/WorkbenchView/WorkbenchView.test.tsx`
- Create: `frontend/src/views/LibraryView/LibraryView.test.tsx`

**Interfaces:**
- Consumes: `useRunEvents(runId, { onTerminal })`.
- Preserves: public component props and existing API modules.

- [ ] **Step 1: Write failing terminal-flow tests**

Mock API modules and `useRunEvents`. Assert:

```ts
it('appends one successful answer and keeps the current conversation', async () => {
  // render Workbench, select/create a conversation, invoke captured onTerminal,
  // expect answer text and composer still associated with that conversation
})

it('clears library busy state and refreshes after success', async () => {
  // start from mocked active run, invoke captured onTerminal, expect list API again
})
```

- [ ] **Step 2: Prove current consumers fail the callback tests**

Run: `npm run test:run -- src/views/WorkbenchView/WorkbenchView.test.tsx src/views/LibraryView/LibraryView.test.tsx`

Expected: failure because consumers still inspect terminal events in effects.

- [ ] **Step 3: Refactor terminal consumption**

Replace the Workbench and Library terminal `useEffect` blocks with memoized `onTerminal` callbacks passed into `useRunEvents`. Preserve success/error copy and refresh behavior exactly.

- [ ] **Step 4: Refactor initial loads**

For Workbench, Library, Graph, and Settings, stop calling a state-changing `refresh` function directly from an effect. Each initial effect must call the underlying request and update state only from promise completion callbacks, with a local cancelled flag in cleanup. Manual refresh buttons may continue using their callback functions.

- [ ] **Step 5: Verify lint and tests**

Run:

```powershell
npm run lint
npm run test:run
```

Expected: zero ESLint errors and all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/hooks frontend/src/views
git commit -m "fix(frontend): make run state event-driven"
```

### Task 4: Lazy-load GraphView without losing state

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: named export `GraphView` from `views/GraphView/GraphView`.
- Produces: graph chunk requested only after first graph navigation.

- [ ] **Step 1: Add a failing activation test**

Mock the GraphView module and assert it is absent on initial Workbench render, appears after the graph tab is selected, and remains mounted after switching away.

- [ ] **Step 2: Prove current eager import fails**

Run: `npm run test:run -- src/App.test.tsx`

Expected: initial render loads GraphView.

- [ ] **Step 3: Implement lazy activation**

Use:

```ts
const LazyGraphView = lazy(() =>
  import('./views/GraphView/GraphView').then((module) => ({ default: module.GraphView })),
)
```

Add `graphActivated` state. The TopBar change handler sets it to true before selecting `graph`; once true, keep the graph pane mounted and use `hidden` for later switches. Wrap only that pane in `Suspense` with an accessible loading message.

- [ ] **Step 4: Verify bundle boundaries**

Run: `npm run build`

Expected: build succeeds; the entry JS chunk is below 500 KB and a separate GraphView/Cytoscape async chunk exists.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "perf(frontend): lazy-load graph workspace"
```

### Task 5: Document and run the complete frontend gate

**Files:**
- Modify: `frontend/DEVLOG.md`

- [ ] **Step 1: Add one 2026-07-11 DEVLOG entry**

Use the required five-field template and explain Vitest, terminal callbacks, lint enforcement, and lazy chunks.

- [ ] **Step 2: Run all gates**

```powershell
npm run lint
npm run typecheck
npm run test:run
npm run build
git diff --check main...HEAD
```

Expected: all commands exit 0; entry JS is below 500 KB.

- [ ] **Step 3: Commit and hand off**

```powershell
git add frontend/DEVLOG.md
git commit -m "docs(frontend): record quality gate upgrade"
git status --short
```

Expected: clean worktree. Report commits, test counts, and build chunk sizes to the main agent.


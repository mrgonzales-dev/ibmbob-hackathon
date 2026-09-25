<script setup>
const sessions = [
  {
    name: 'bob-pr',
    tag: 'live',
    state: 'idle — task done',
    lines: [
      { cls: 'usr', text: '› /bob-pr add a projects section to the portfolio' },
      { cls: 'thk', text: '⠿ skill bob-pr loaded — planning...' },
      { cls: 'tol', text: '◆ bob_pr new --files main.go,index.html,style.css' },
      { cls: 'res', text: '  → PR #1 created' },
      { cls: 'tol', text: '◆ bob_pr snapshot 1' },
      { cls: 'res', text: '  → 3 files → .bob-pr/tmp/1/' },
      { cls: 'tol', text: '◆ edit shadow copies (main.go, index.html, style.css)' },
      { cls: 'tol', text: '◆ bob_pr diff 1' },
      { cls: 'res', text: '  → 3 diffs computed' },
      { cls: 'tol', text: '◆ bob_pr serve' },
      { cls: 'res', text: '  → review at localhost:2428/pr/1' },
      { cls: 'wat', text: '⏸ waiting — review the plan...' },
      { cls: 'okl', text: '✓ APPROVED' },
      { cls: 'tol', text: '◆ bob_pr apply 1' },
      { cls: 'okl', text: '✓ APPLIED: 3 files' },
    ],
  },
  {
    name: 'bob-upgrade',
    tag: 'wip — simulated',
    state: 'idle — task done',
    lines: [
      { cls: 'usr', text: '› /bob-upgrade upgrade our dependencies' },
      { cls: 'thk', text: '⠿ skill bob-upgrade loaded — scanning...' },
      { cls: 'tol', text: '◆ bob_upgrade scan' },
      { cls: 'res', text: '  → vue 3.4→3.5 safe' },
      { cls: 'res', text: '  → vite 5.x→8.x breaking' },
      { cls: 'tol', text: '◆ bob_upgrade run vite --dry-run' },
      { cls: 'res', text: '  → build passes' },
      { cls: 'tol', text: '◆ bob_pr open-pr "chore: bump vite"' },
      { cls: 'res', text: '  → PR #2 opened for review' },
      { cls: 'wat', text: '⏸ waiting — review the plan...' },
      { cls: 'okl', text: '✓ APPROVED' },
      { cls: 'okl', text: '✓ APPLIED — tests green' },
    ],
  },
  {
    name: 'bob-test',
    tag: 'soon — simulated',
    state: 'needs revision',
    lines: [
      { cls: 'usr', text: '› /bob-test write tests for src/auth.py' },
      { cls: 'thk', text: '⠿ skill bob-test loaded — generating...' },
      { cls: 'tol', text: '◆ bob_test gen src/auth.py' },
      { cls: 'res', text: '  → 4 tests → test_auth.py' },
      { cls: 'tol', text: '◆ bob_test run' },
      { cls: 'res', text: '  → 17 passed · cov 82%' },
      { cls: 'tol', text: '◆ bob_pr open-pr "test: auth cases"' },
      { cls: 'res', text: '  → PR #3 opened' },
      { cls: 'wat', text: '⏸ waiting — review the plan...' },
      { cls: 'bad', text: '✗ CHANGES REQUESTED' },
      { cls: 'res', text: '  → "add a null-token case"' },
      { cls: 'tol', text: '◆ bob_test gen --add null-token' },
      { cls: 'okl', text: '✓ revision 2 pushed' },
    ],
  },
]
</script>

<template>
  <div class="terms" id="demo">
    <div v-for="(s, si) in sessions" :key="s.name" class="term">
      <div class="term-bar">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        <span class="term-title">{{ s.name }}</span>
        <span class="term-tag">{{ s.tag }}</span>
      </div>
      <div class="term-body">
        <p
          v-for="(l, i) in s.lines"
          :key="i"
          class="line"
          :class="l.cls"
          :style="{ '--d': si * 0.6 + i * 0.35 + 's' }"
        >{{ l.text }}</p>
      </div>
      <div class="term-status">
        <span class="cursor">▌</span> agent {{ s.state }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.terms {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  text-align: left;
}

.term {
  border: 3px solid var(--ink);
  box-shadow: 6px 6px 0 var(--blue);
  background: #07090f;
  font-size: 12.5px;
  overflow: hidden;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.term:nth-child(2) { box-shadow: 6px 6px 0 var(--purple); }
.term:nth-child(3) { box-shadow: 6px 6px 0 var(--dim); }

.term-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 2px solid var(--dim);
  background: var(--panel);
}

.dot {
  width: 9px;
  height: 9px;
  border: 2px solid var(--ink);
  flex-shrink: 0;
}
.dot:nth-child(1) { background: var(--purple); }
.dot:nth-child(2) { background: var(--blue); }
.dot:nth-child(3) { background: var(--dim); }

.term-title {
  margin-left: 6px;
  color: var(--ink);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
}

.term-tag {
  margin-left: auto;
  color: var(--purple);
  font-size: 10px;
  letter-spacing: 1px;
}

.term-body {
  padding: 14px 14px 8px;
  flex: 1;
}

.term-status {
  border-top: 2px solid var(--dim);
  background: var(--panel);
  padding: 8px 14px;
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 1px;
}

.line {
  margin: 0 0 7px;
  white-space: pre-wrap;
  word-break: break-all;
  opacity: 0;
  animation: type-in 0.01s var(--d) forwards;
}

.usr { color: var(--blue); font-weight: 700; }
.thk { color: var(--purple); }
.tol { color: var(--ink); }
.res { color: var(--muted); }
.wat { color: #facc15; }
.okl { color: #4ade80; }
.bad { color: #f87171; }

.cursor { animation: blink 1s steps(1) infinite; color: var(--blue); }

@keyframes type-in { to { opacity: 1; } }
@keyframes blink { 50% { opacity: 0; } }

@media (max-width: 1000px) {
  .terms { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .line { animation: none; opacity: 1; }
  .cursor { animation: none; }
}
</style>

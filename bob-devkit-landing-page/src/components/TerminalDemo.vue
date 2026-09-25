<script setup>
const sessions = [
  {
    name: 'bob-pr',
    tag: 'live',
    lines: [
      { cls: 'cmd', text: '$ bob_pr new --title "Add projects" --files main.go,index.html' },
      { cls: 'out', text: 'PR #1 created' },
      { cls: 'cmd', text: '$ bob_pr snapshot 1' },
      { cls: 'out', text: 'copied → .bob-pr/tmp/1/' },
      { cls: 'cmd', text: '$ bob_pr diff 1' },
      { cls: 'out', text: 'diffs computed from real files' },
      { cls: 'cmd', text: '$ bob_pr serve' },
      { cls: 'out', text: 'localhost:2428/pr/1' },
      { cls: 'dim', text: '# you approve...' },
      { cls: 'cmd', text: '$ bob_pr apply 1' },
      { cls: 'ok',  text: 'APPLIED: 3 files' },
    ],
  },
  {
    name: 'bob-upgrade',
    tag: 'wip — simulated',
    lines: [
      { cls: 'dim', text: '# simulated session' },
      { cls: 'cmd', text: '$ bob_upgrade scan' },
      { cls: 'out', text: 'vue  3.4 → 3.5  safe' },
      { cls: 'out', text: 'vite 5.x → 8.x  breaking' },
      { cls: 'cmd', text: '$ bob_upgrade run vite' },
      { cls: 'out', text: 'dry-run: build passes' },
      { cls: 'cmd', text: '$ bob_upgrade open-pr' },
      { cls: 'out', text: 'PR #2 "bump vite" opened' },
      { cls: 'dim', text: '# you approve...' },
      { cls: 'ok',  text: 'APPLIED — green' },
    ],
  },
  {
    name: 'bob-test',
    tag: 'soon — simulated',
    lines: [
      { cls: 'dim', text: '# simulated session' },
      { cls: 'cmd', text: '$ bob_test gen src/auth.py' },
      { cls: 'out', text: '4 tests → test_auth.py' },
      { cls: 'cmd', text: '$ bob_test run' },
      { cls: 'out', text: '17 passed · cov 82%' },
      { cls: 'cmd', text: '$ bob_test open-pr' },
      { cls: 'out', text: 'PR #3 opened' },
      { cls: 'dim', text: '# you: add null-token case' },
      { cls: 'out', text: 'revision 2 pushed' },
      { cls: 'ok',  text: 'APPLIED — 18 pass' },
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
          :style="{ '--d': si * 0.5 + i * 0.35 + 's' }"
        >{{ l.text }}</p>
        <p class="line" :style="{ '--d': si * 0.5 + s.lines.length * 0.35 + 's' }">$ <span class="cursor">▌</span></p>
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
  font-size: 13px;
  overflow: hidden;
  min-width: 0;
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
  padding: 12px 12px 16px;
  min-height: 270px;
}

.line {
  margin: 0 0 5px;
  white-space: pre-wrap;
  word-break: break-all;
  opacity: 0;
  animation: type-in 0.01s var(--d) forwards;
}

.cmd { color: var(--ink); }
.out { color: var(--muted); }
.dim { color: #4a5068; font-style: italic; }
.ok  { color: #4ade80; }

.cursor { animation: blink 1s steps(1) infinite; color: var(--blue); }

@keyframes type-in { to { opacity: 1; } }
@keyframes blink { 50% { opacity: 0; } }

@media (max-width: 900px) {
  .terms { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .line { animation: none; opacity: 1; }
  .cursor { animation: none; }
}
</style>

<script setup>
import { ref } from 'vue'

const sessions = {
  'bob-pr': [
    { cls: 'cmd', text: '$ bob_pr new --title "Add projects section" --files main.go,index.html,style.css' },
    { cls: 'out', text: 'PR #1 created — revision 1' },
    { cls: 'cmd', text: '$ bob_pr snapshot 1 && bob_pr diff 1' },
    { cls: 'out', text: '3 files copied → .bob-pr/tmp/1/  (sha256 recorded)' },
    { cls: 'out', text: '3 diffs computed from real file content' },
    { cls: 'cmd', text: '$ bob_pr serve' },
    { cls: 'out', text: 'review at http://localhost:2428/pr/1' },
    { cls: 'dim', text: '# you click Approve in the browser...' },
    { cls: 'cmd', text: '$ bob_pr apply 1' },
    { cls: 'ok',  text: 'APPLIED: main.go · index.html · style.css' },
  ],
  'bob-upgrade': [
    { cls: 'dim', text: '# simulated — skill in development' },
    { cls: 'cmd', text: '$ bob_upgrade scan' },
    { cls: 'out', text: 'vue   3.4.0 → 3.5.x   safe' },
    { cls: 'out', text: 'vite  5.x   → 8.x     breaking' },
    { cls: 'out', text: '3 updates found' },
    { cls: 'cmd', text: '$ bob_upgrade run vite --dry-run' },
    { cls: 'out', text: 'simulating... 2 files touched, build passes' },
    { cls: 'cmd', text: '$ bob_upgrade open-pr' },
    { cls: 'out', text: 'bob-pr #2 "chore: bump vite" opened for review' },
    { cls: 'dim', text: '# you click Approve...' },
    { cls: 'ok',  text: 'APPLIED — upgrade complete, tests green' },
  ],
  'bob-test': [
    { cls: 'dim', text: '# simulated — skill slot reserved' },
    { cls: 'cmd', text: '$ bob_test gen src/auth.py' },
    { cls: 'out', text: '4 tests written → tests/test_auth.py' },
    { cls: 'cmd', text: '$ bob_test run' },
    { cls: 'out', text: '17 passed · 0 failed · coverage 82%' },
    { cls: 'cmd', text: '$ bob_test open-pr' },
    { cls: 'out', text: 'bob-pr #3 "test: cover auth edge cases" opened' },
    { cls: 'dim', text: '# you request changes: "add null-token case"' },
    { cls: 'out', text: 'revision 2 pushed — re-review pending' },
    { cls: 'ok',  text: 'APPLIED — 18 passing' },
  ],
}

const tabs = Object.keys(sessions)
const active = ref(tabs[0])
</script>

<template>
  <div class="term" id="demo">
    <div class="term-bar">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      <div class="tabs">
        <button
          v-for="t in tabs"
          :key="t"
          class="tab"
          :class="{ on: active === t }"
          @click="active = t"
        >{{ t }}</button>
      </div>
    </div>
    <div class="term-body" :key="active">
      <p
        v-for="(l, i) in sessions[active]"
        :key="i"
        class="line"
        :class="l.cls"
        :style="{ '--d': i * 0.4 + 's' }"
      >{{ l.text }}</p>
      <p class="line" :style="{ '--d': sessions[active].length * 0.4 + 's' }">$ <span class="cursor">▌</span></p>
    </div>
  </div>
</template>

<style scoped>
.term {
  border: 3px solid var(--ink);
  box-shadow: 10px 10px 0 var(--blue);
  background: #07090f;
  font-size: 13.5px;
  overflow: hidden;
  text-align: left;
}

.term-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 2px solid var(--dim);
  background: var(--panel);
}

.dot {
  width: 11px;
  height: 11px;
  border: 2px solid var(--ink);
}
.dot:nth-child(1) { background: var(--purple); }
.dot:nth-child(2) { background: var(--blue); }
.dot:nth-child(3) { background: var(--dim); }

.tabs { display: flex; gap: 6px; margin-left: 12px; }

.tab {
  font: inherit;
  font-size: 12px;
  letter-spacing: 1px;
  padding: 4px 12px;
  border: 2px solid var(--dim);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  text-transform: lowercase;
  transition: all 150ms ease;
}

.tab:hover { color: var(--ink); border-color: var(--ink); }

.tab.on {
  background: var(--blue);
  border-color: var(--blue);
  color: #fff;
}

.term-body {
  padding: 16px 18px;
  min-height: 300px;
}

.line {
  margin: 0 0 6px;
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

@media (prefers-reduced-motion: reduce) {
  .line { animation: none; opacity: 1; }
  .cursor { animation: none; }
}
</style>

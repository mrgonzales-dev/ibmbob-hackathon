<script setup>
const lines = [
  { cls: 'cmd', text: '$ bob_pr new --title "Add projects section" --files main.go,index.html,style.css' },
  { cls: 'out', text: 'PR #1 created — revision 1' },
  { cls: 'cmd', text: '$ bob_pr snapshot 1' },
  { cls: 'out', text: '3 files copied → .bob-pr/tmp/1/  (sha256 recorded)' },
  { cls: 'dim', text: '# agent edits the shadow copies...' },
  { cls: 'cmd', text: '$ bob_pr diff 1' },
  { cls: 'out', text: '3 diffs computed from real file content' },
  { cls: 'cmd', text: '$ bob_pr serve' },
  { cls: 'out', text: 'Review at http://localhost:2428/pr/1' },
  { cls: 'dim', text: '# user clicks Approve in the browser...' },
  { cls: 'cmd', text: '$ bob_pr decision 1' },
  { cls: 'ok',  text: 'APPROVED (revision 2)' },
  { cls: 'cmd', text: '$ bob_pr apply 1' },
  { cls: 'ok',  text: 'APPLIED: main.go · index.html · style.css' },
]
</script>

<template>
  <div class="term" id="demo">
    <div class="term-bar">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      <span class="term-title">bob-pr — plan review session</span>
    </div>
    <div class="term-body">
      <p
        v-for="(l, i) in lines"
        :key="i"
        class="line"
        :class="l.cls"
        :style="{ '--d': i * 0.45 + 's' }"
      >{{ l.text }}</p>
      <p class="line cursor-line" :style="{ '--d': lines.length * 0.45 + 's' }">$ <span class="cursor">▌</span></p>
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

.term-title {
  margin-left: 8px;
  color: var(--muted);
  font-size: 12px;
  letter-spacing: 1px;
}

.term-body { padding: 16px 18px; }

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

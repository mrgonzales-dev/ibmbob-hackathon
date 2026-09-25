<script setup>
const lines = [
  { cls: 'usr', text: '$ bobdevkit install' },
  { cls: 'res', text: 'detecting agent environments...' },
  { cls: 'res', text: '  found: ibm-bob-2.0, windsurf, cursor' },
  { cls: 'prm', text: '' },
  { cls: 'prm', text: '? which agent do you use?' },
  { cls: 'sel', text: '  ❯ IBM Bob 2.0' },
  { cls: 'opt', text: '    Windsurf' },
  { cls: 'opt', text: '    Cursor' },
  { cls: 'opt', text: '    Devin' },
  { cls: 'prm', text: '' },
  { cls: 'prm', text: '? which skills? (space to toggle)' },
  { cls: 'chk', text: '  [x] bob-pr        plan review gate' },
  { cls: 'chk', text: '  [x] bob-upgrade   dependency upgrades' },
  { cls: 'opt', text: '  [ ] bob-test      test generation' },
  { cls: 'prm', text: '' },
  { cls: 'res', text: 'installing 2 skills → ~/.bob/skills/' },
  { cls: 'okl', text: '✓ bob-pr       installed' },
  { cls: 'okl', text: '✓ bob-upgrade  installed' },
  { cls: 'okl', text: '✓ done — restart your agent' },
]
</script>

<template>
  <section class="install" id="install">
    <h2 class="reveal">install</h2>
    <p class="hint reveal">One command. Pick your agent, pick your skills.</p>
    <div class="term reveal">
      <div class="term-bar">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        <span class="term-title">bobdevkit — installer</span>
      </div>
      <div class="term-body">
        <p
          v-for="(l, i) in lines"
          :key="i"
          class="line"
          :class="l.cls"
          :style="{ '--d': i * 0.3 + 's' }"
        >{{ l.text || ' ' }}</p>
        <p class="line" :style="{ '--d': lines.length * 0.3 + 's' }">$ <span class="cursor">▌</span></p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.install {
  max-width: 720px;
  margin: 0 auto;
  padding: 64px 24px;
}

h2 {
  font-size: clamp(28px, 5vw, 44px);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin: 0 0 12px;
  border-bottom: 4px solid var(--blue);
  padding-bottom: 12px;
}

.hint {
  color: var(--muted);
  font-size: 15px;
  margin: 0 0 36px;
}

.term {
  border: 3px solid var(--ink);
  box-shadow: 10px 10px 0 var(--purple);
  background: #07090f;
  font-size: 13.5px;
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

.term-title {
  margin-left: 8px;
  color: var(--muted);
  font-size: 12px;
  letter-spacing: 1px;
}

.term-body { padding: 16px 18px; }

.line {
  margin: 0 0 5px;
  white-space: pre-wrap;
  opacity: 0;
  animation: type-in 0.01s var(--d) forwards;
}

.usr { color: var(--ink); font-weight: 700; }
.prm { color: var(--blue); font-weight: 700; }
.sel { color: #fff; background: var(--blue); font-weight: 700; }
.opt { color: var(--muted); }
.chk { color: var(--purple); }
.res { color: var(--muted); }
.okl { color: #4ade80; }

.cursor { animation: blink 1s steps(1) infinite; color: var(--blue); }

@keyframes type-in { to { opacity: 1; } }
@keyframes blink { 50% { opacity: 0; } }

@media (prefers-reduced-motion: reduce) {
  .line { animation: none; opacity: 1; }
  .cursor { animation: none; }
}
</style>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import prDoc from '../../../bobdevkit/bob-pr/SKILL.md?raw'
import upgradeDoc from '../../../bobdevkit/bob-upgrade-check/SKILL.md?raw'
import impactDoc from '../../../bobdevkit/bob-impact/SKILL.md?raw'

const props = defineProps({ name: String })

const docs = {
  'bob-pr': prDoc,
  'bob-upgrade-check': upgradeDoc,
  'bob-impact': impactDoc,
}

const html = computed(() => {
  const md = docs[props.name]
  return md ? marked.parse(md.replace(/^---\n[\s\S]*?\n---\n/, '')) : ''
})
</script>

<template>
  <section class="doc">
    <a class="back" href="#skills">&#8592; all skills</a>
    <div v-if="html" class="page" v-html="html" />
    <p v-else class="page empty">
      unknown skill "{{ name }}" — <a href="#skills">browse the skills</a>
    </p>
  </section>
</template>

<style scoped>
.doc {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 24px 80px;
}

.back {
  display: inline-block;
  color: var(--muted);
  text-decoration: none;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 1px;
  border: 2px solid var(--dim);
  padding: 6px 14px;
  margin-bottom: 32px;
  transition: color 150ms ease, border-color 150ms ease;
}

.back:hover {
  color: var(--ink);
  border-color: var(--blue);
}

.page {
  border: 2px solid var(--ink);
  background: var(--panel);
  box-shadow: 8px 8px 0 var(--dim);
  padding: 36px 40px;
  line-height: 1.7;
  font-size: 15px;
}

.page :deep(h1) {
  margin: 0 0 20px;
  font-size: 30px;
  text-transform: uppercase;
  letter-spacing: 2px;
  border-bottom: 3px solid var(--blue);
  padding-bottom: 12px;
}

.page :deep(h2) {
  margin: 32px 0 12px;
  font-size: 19px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--blue);
}

.page :deep(h3) {
  margin: 24px 0 10px;
  font-size: 16px;
  letter-spacing: 1px;
}

.page :deep(p) {
  margin: 0 0 14px;
  color: var(--muted);
}

.page :deep(li) {
  color: var(--muted);
  margin-bottom: 6px;
}

.page :deep(ul),
.page :deep(ol) {
  margin: 0 0 14px;
  padding-left: 24px;
}

.page :deep(code) {
  background: var(--bg);
  border: 1px solid var(--dim);
  padding: 1px 6px;
  font-size: 13px;
  color: var(--ink);
}

.page :deep(pre) {
  background: var(--bg);
  border: 2px solid var(--ink);
  box-shadow: 6px 6px 0 var(--dim);
  padding: 16px 18px;
  overflow-x: auto;
  margin: 0 0 16px;
}

.page :deep(pre code) {
  background: none;
  border: 0;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}

.page :deep(table) {
  border-collapse: collapse;
  margin: 0 0 16px;
  width: 100%;
  font-size: 13px;
}

.page :deep(th),
.page :deep(td) {
  border: 1px solid var(--dim);
  padding: 8px 12px;
  text-align: left;
}

.page :deep(th) {
  color: var(--blue);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-size: 12px;
}

.page :deep(td) { color: var(--muted); }

.page :deep(a) { color: var(--blue); }

.page :deep(strong) { color: var(--ink); }

.page :deep(blockquote) {
  border-left: 3px solid var(--purple);
  margin: 0 0 14px;
  padding: 4px 16px;
  color: var(--muted);
}

.empty { color: var(--muted); }
.empty a { color: var(--blue); }
</style>

<script setup>
const steps = [
  ['plan', 'The agent writes a plan and opens it as a pull request.'],
  ['snapshot', 'Real files are copied to a shadow workspace — your tree stays clean.'],
  ['review', 'You read computed diffs in a local review page. Approve or request changes.'],
  ['apply', 'Approved copies swap in atomically. Stale files are refused.'],
]
</script>

<template>
  <section class="workflow" id="workflow">
    <h2 class="reveal">how it works</h2>
    <ol class="steps">
      <li v-for="(s, i) in steps" :key="i" class="step reveal">
        <span class="step-num">{{ String(i + 1).padStart(2, '0') }}</span>
        <div>
          <h3>{{ s[0] }}</h3>
          <p>{{ s[1] }}</p>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.workflow {
  max-width: 760px;
  margin: 0 auto;
  padding: 64px 24px 96px;
}

h2 {
  font-size: clamp(28px, 5vw, 44px);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin: 0 0 40px;
  border-bottom: 4px solid var(--purple);
  padding-bottom: 12px;
}

.steps {
  list-style: none;
  margin: 0;
  padding: 0;
}

.step {
  display: flex;
  gap: 24px;
  align-items: baseline;
  border-left: 5px solid var(--dim);
  padding: 18px 0 18px 20px;
}

.step-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--blue);
  min-width: 48px;
}

.step h3 {
  margin: 0 0 6px;
  font-size: 18px;
  text-transform: uppercase;
  letter-spacing: 2px;
}

.step p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}
</style>

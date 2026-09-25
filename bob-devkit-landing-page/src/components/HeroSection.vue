<script setup>
import TerminalDemo from './TerminalDemo.vue'
</script>

<template>
  <section class="hero" id="top">
    <p class="sys reveal">sys://skills.collection</p>
    <h1 class="reveal">
      Supercharge<br />
      <span class="grad">Bob 2.0</span>
    </h1>
    <p class="sub reveal">
      A skill kit for the Bob 2.0 IDE. Real gates, not vibes.
    </p>
    <div class="cta-row reveal">
      <a class="btn primary" href="#skills">browse the skills</a>
      <a class="btn" href="#workflow">how it works</a>
    </div>
    <div class="term-wrap reveal">
      <TerminalDemo />
    </div>
  </section>
</template>

<style scoped>
.hero {
  max-width: 1440px;
  margin: 0 auto;
  padding: 96px 32px 80px;
  text-align: center;
}

.sys {
  color: var(--blue);
  font-size: 13px;
  letter-spacing: 2px;
  margin: 0 0 24px;
}

h1 {
  margin: 0;
  font-size: clamp(44px, 9vw, 88px);
  text-transform: uppercase;
  letter-spacing: 2px;
  line-height: 0.95;
}

.grad {
  background: linear-gradient(90deg, var(--blue), var(--purple));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.sub {
  color: var(--muted);
  font-size: 16px;
  line-height: 1.7;
  max-width: 560px;
  margin: 28px auto 0;
}

.sub code {
  color: var(--blue);
  border: 1px solid var(--dim);
  padding: 1px 6px;
}

.cta-row {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin: 36px 0 56px;
  flex-wrap: wrap;
}

.btn {
  display: inline-block;
  padding: 14px 28px;
  border: 3px solid var(--ink);
  color: var(--ink);
  text-decoration: none;
  text-transform: uppercase;
  font-size: 14px;
  letter-spacing: 2px;
  box-shadow: 6px 6px 0 var(--dim);
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 8px 8px 0 var(--purple);
}

.btn.primary {
  background: linear-gradient(90deg, var(--blue), var(--purple));
  border-color: transparent;
  color: #fff;
  box-shadow: 6px 6px 0 var(--dim);
}

.term-wrap {
  margin: 0 auto;
  text-align: left;
}
</style>

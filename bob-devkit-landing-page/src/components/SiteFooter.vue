<template>
  <footer class="foot">
    <div class="cols">
      <div class="col brand">
        <p class="logo">BOB<span>DEVKIT</span></p>
        <p class="tag">Agentic skillset for developer workflows.</p>
      </div>
      <div class="col">
        <p class="head">skills</p>
        <a href="#skills">bob-pr</a>
        <a href="#skills">bob-upgrade</a>
        <a href="#skills">bob-test</a>
      </div>
      <div class="col">
        <p class="head">project</p>
        <a href="https://github.com/mrgonzales-dev/ibmbob-hackathon">github</a>
        <a href="#workflow">workflow</a>
        <a href="#demo">demo</a>
      </div>
    </div>
    <p class="base">built for IBM Bob 2.0 — hackathon prototype</p>
  </footer>
</template>

<style scoped>
.foot {
  border-top: 3px solid var(--ink);
  padding: 48px 32px 32px;
  background: var(--panel);
}

.cols {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 32px;
  max-width: 1000px;
  margin: 0 auto 40px;
}

.logo {
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 2px;
  margin: 0 0 8px;
  text-transform: uppercase;
}

.logo span {
  background: linear-gradient(90deg, var(--blue), var(--purple));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.tag {
  color: var(--muted);
  font-size: 13px;
  margin: 0;
}

.head {
  color: var(--blue);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin: 0 0 12px;
}

.col a {
  display: block;
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  margin-bottom: 8px;
  transition: color 150ms ease;
}

.col a:hover { color: var(--ink); }

.base {
  text-align: center;
  color: #4a5068;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin: 0;
  border-top: 1px solid var(--dim);
  padding-top: 24px;
}

@media (max-width: 640px) {
  .cols { grid-template-columns: 1fr; }
}
</style>

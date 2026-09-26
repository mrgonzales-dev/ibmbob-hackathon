<template>
  <header class="nav">
    <a class="logo" href="#top">Bob<span>devkit</span></a>
    <nav class="links">
      <a href="#demo">demo</a>
      <a href="#install">install</a>
      <a href="#skills">skills</a>
      <a href="#workflow">workflow</a>
      <a class="gh" href="https://github.com/mrgonzales-dev/ibmbob-hackathon">github</a>
    </nav>
  </header>
</template>

<style scoped>
.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 32px;
  border-bottom: 3px solid var(--ink);
  background: var(--bg);
}

.logo {
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 1px;
  color: var(--ink);
  text-decoration: none;
}

.logo span {
  background: linear-gradient(90deg, var(--blue), var(--purple));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.links {
  display: flex;
  gap: 24px;
}

.links a {
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: color 150ms ease;
}

.links a:hover { color: var(--ink); }

.links .gh {
  color: var(--blue);
  border: 2px solid var(--blue);
  padding: 2px 10px;
}

.links .gh:hover {
  background: var(--blue);
  color: var(--bg);
}
</style>

<script setup>
const skills = [
  {
    num: '01',
    name: 'bob-pr',
    status: 'live',
    desc: 'Plans shipped as pull requests. Shadow copies become real diffs. You approve, it applies — atomically.',
  },
  {
    num: '02',
    name: 'bob-upgrade-check',
    status: 'live',
    desc: 'Dependency and stack upgrades handled by the agent, gated by review.',
  },
  {
    num: '03',
    name: 'bob-impact',
    status: 'live',
    desc: 'Blast radius before you merge. Traces callers, tables, and tests from git diff.',
  },
]
</script>

<template>
  <section class="skills" id="skills">
    <h2 class="reveal">the skills</h2>
    <div class="grid">
      <article
        v-for="s in skills"
        :key="s.name"
        class="card reveal"
        :data-status="s.status"
      >
        <p class="num">#{{ s.num }} <span class="status">[{{ s.status }}]</span></p>
        <h3>{{ s.name }}</h3>
        <p class="desc">{{ s.desc }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.skills {
  max-width: 1000px;
  margin: 0 auto;
  padding: 64px 24px;
}

h2 {
  font-size: clamp(28px, 5vw, 44px);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin: 0 0 40px;
  border-bottom: 4px solid var(--blue);
  padding-bottom: 12px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}

.card {
  border: 2px solid var(--ink);
  padding: 22px 20px;
  background: var(--panel);
  box-shadow: 6px 6px 0 var(--dim);
  transition: transform 200ms ease, box-shadow 200ms ease;
}

.card:hover {
  transform: translate(-2px, -2px);
  box-shadow: 8px 8px 0 var(--blue);
}

.card[data-status="wip"]:hover { box-shadow: 8px 8px 0 var(--purple); }
.card[data-status="soon"] { opacity: 0.45; border-style: dashed; }

.num {
  color: var(--blue);
  font-size: 13px;
  margin: 0 0 12px;
  letter-spacing: 1px;
}

.status { color: var(--purple); }

h3 {
  margin: 0 0 10px;
  font-size: 20px;
  text-transform: uppercase;
  letter-spacing: 2px;
}

.desc {
  margin: 0;
  font-size: 14px;
  color: var(--muted);
  line-height: 1.6;
}
</style>

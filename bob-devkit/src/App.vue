<script setup>
const skills = [
  {
    name: 'bob-pr',
    status: 'live',
    desc: 'Plans shipped as pull requests. Review diffs, approve, apply.',
  },
  {
    name: 'bob-test',
    status: 'soon',
    desc: 'Skill slot reserved.',
  },
  {
    name: 'bob-docs',
    status: 'soon',
    desc: 'Skill slot reserved.',
  },
]
</script>

<template>
  <section class="hero">
    <p class="sys">sys://skills.collection</p>
    <h1>BOB DEVKIT</h1>
    <p class="tagline">// agentic skillset for developer workflows</p>
    <p class="blurb">
      A growing kit of agent skills that gate, review, and automate the slow
      parts of software work. Each skill runs per-project. No global state.
    </p>
    <ul class="skill-list">
      <li v-for="s in skills" :key="s.name" class="skill" :data-status="s.status">
        <span class="skill-name">{{ s.name }}</span>
        <span class="skill-status">[{{ s.status }}]</span>
        <p class="skill-desc">{{ s.desc }}</p>
      </li>
    </ul>
    <p class="foot">built for IBM Bob 2.0 — hackathon prototype</p>
  </section>
</template>

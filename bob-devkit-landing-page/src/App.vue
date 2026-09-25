<script setup>
import { onMounted } from 'vue'
import NavBar from './components/NavBar.vue'
import HeroSection from './components/HeroSection.vue'
import SkillGrid from './components/SkillGrid.vue'
import WorkflowSection from './components/WorkflowSection.vue'
import SiteFooter from './components/SiteFooter.vue'

onMounted(() => {
  const observer = new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => e.isIntersecting && e.target.classList.add('visible')),
    { threshold: 0.15 }
  )
  document.querySelectorAll('.reveal').forEach((el) => observer.observe(el))
})
</script>

<template>
  <NavBar />
  <main>
    <HeroSection />
    <SkillGrid />
    <WorkflowSection />
  </main>
  <SiteFooter />
</template>

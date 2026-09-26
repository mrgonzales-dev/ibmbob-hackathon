<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import NavBar from './components/NavBar.vue'
import HeroSection from './components/HeroSection.vue'
import InstallSection from './components/InstallSection.vue'
import SkillGrid from './components/SkillGrid.vue'
import SkillDoc from './components/SkillDoc.vue'
import SiteFooter from './components/SiteFooter.vue'

const hash = ref(location.hash)
const doc = computed(() => hash.value.match(/^#\/docs\/([\w-]+)/)?.[1])

let observer
const observe = () =>
  document
    .querySelectorAll('.reveal:not(.visible)')
    .forEach((el) => observer.observe(el))

const onHash = async () => {
  hash.value = location.hash
  await nextTick()
  if (doc.value) {
    scrollTo(0, 0)
  } else {
    observe()
    document.getElementById(location.hash.slice(1))?.scrollIntoView()
  }
}

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => e.isIntersecting && e.target.classList.add('visible')),
    { threshold: 0.15 }
  )
  observe()
  addEventListener('hashchange', onHash)
})

onUnmounted(() => removeEventListener('hashchange', onHash))
</script>

<template>
  <NavBar />
  <main>
    <SkillDoc v-if="doc" :name="doc" />
    <template v-else>
      <HeroSection />
      <InstallSection />
      <SkillGrid />
    </template>
  </main>
  <SiteFooter />
</template>

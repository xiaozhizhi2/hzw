<template>
  <div class="dashboard">
    <header>
      <h1>🐄 Cow Dashboard</h1>
      <div class="header-meta">
        <span class="herdr-badge" :class="{ connected: herdrConnected }">
          {{ herdrConnected ? 'herdr' : 'mock' }}
        </span>
        <span class="count">{{ agents.length }} agents</span>
        <span class="updated">{{ lastUpdate }}</span>
      </div>
    </header>

    <div class="grid">
      <div
        v-for="a in agents"
        :key="a.id"
        class="card"
        :class="a.status"
      >
        <div class="cow-wrapper">
          <CowFace :status="a.status" />
        </div>
        <div class="info">
          <div class="name">{{ a.name }}</div>
          <div class="status" :class="a.status">
            {{ statusText(a.status) }}
          </div>
        </div>
        <div class="uptime" v-if="a.uptime">
          {{ fmtUptime(a.uptime) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import CowFace from './CowFace.vue'

const agents = ref([])
const herdrConnected = ref(false)
const lastUpdate = ref('--')
let timer = null

const statusTexts = {
  idle:    'Idle',
  working: 'Working',
  blocked: 'Blocked',
  done:    'Done',
}

function statusText(status) {
  return statusTexts[status] || status
}

function fmtUptime(sec) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

async function fetchAgents() {
  try {
    const r = await fetch('/api/agents')
    const data = await r.json()
    agents.value = data.agents || []
    herdrConnected.value = data.herdr_connected || false
    lastUpdate.value = new Date(data.timestamp * 1000).toLocaleTimeString()
  } catch {
    agents.value = []
  }
}

onMounted(() => {
  fetchAgents()
  timer = setInterval(fetchAgents, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style>
/* ---------- layout ---------- */
.dashboard {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 20px;
}

/* ---------- header ---------- */
header {
  margin-bottom: 40px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
header h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: #fff;
}
.header-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: #888;
}
.herdr-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  background: #1a1a1a;
  border: 1px solid #333;
  color: #888;
}
.herdr-badge.connected {
  border-color: #22c55e;
  color: #22c55e;
}

/* ---------- grid ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

/* ---------- card ---------- */
.card {
  background: #1a1a1a;
  border-radius: 16px;
  padding: 24px 20px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  border: 1px solid #2a2a2a;
  transition: all 0.3s ease;
}
.card:hover {
  border-color: #444;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}

/* status border glow */
.card.idle    { border-color: #6b7280; }
.card.working { border-color: #22c55e; box-shadow: 0 0 20px rgba(34,197,94,0.12); }
.card.blocked { border-color: #ef4444; box-shadow: 0 0 20px rgba(239,68,68,0.12); }
.card.done    { border-color: #3b82f6; box-shadow: 0 0 20px rgba(59,130,246,0.12); }

/* ---------- cow wrapper ---------- */
.cow-wrapper {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ---------- info ---------- */
.info .name {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 6px;
}
.info .status {
  font-size: 14px;
  font-weight: 500;
  display: inline-block;
  padding: 3px 14px;
  border-radius: 8px;
}
.status.idle    { background: #374151; color: #9ca3af; }
.status.working { background: #14532d; color: #4ade80; }
.status.blocked { background: #450a0a; color: #f87171; }
.status.done    { background: #1e3a5f; color: #60a5fa; }

/* ---------- uptime ---------- */
.uptime {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
</style>

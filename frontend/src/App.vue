<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">轨道交通信号检修管理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向轨道交通信号设备日常巡检、故障处置、天窗修作业、器材检修与联锁试验的一体化信号检修管理后台。</span>
        <label class="role-switch">
          当前岗位
          <select :value="store.role" @change="switchRole(($event.target as HTMLSelectElement).value)">
            <option v-for="item in store.rolePresets" :key="item.role" :value="item.role">
              {{ item.role }} · {{ item.name }}（{{ item.department }}）
            </option>
          </select>
        </label>
        <span class="head-user">{{ store.operator }} · {{ store.department }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import { readActionError, request } from '@/api/client'
import { useSessionStore, type RolePreset } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "技术改造", path: "/transformation" }, { label: "联锁管理", path: "/interlock" }, { label: "轨道电路", path: "/trackcircuit" }, { label: "信号机", path: "/signal" }, { label: "转辙机", path: "/pointmachine" }, { label: "信号电缆", path: "/cable" }, { label: "信号电源", path: "/powersupply" }, { label: "车载设备", path: "/atp" }, { label: "应答器", path: "/balise" }, { label: "计轴设备", path: "/axlecounter" }, { label: "调度中心", path: "/dispatchcenter" }, { label: "天窗修作业", path: "/maintenancewindow" }, { label: "继电器检修", path: "/relay" }, { label: "熔断器管理", path: "/fuse" }, { label: "防雷元件", path: "/lightning" }, { label: "应急备品", path: "/emergencyresp" }, { label: "联锁试验", path: "/testrecord" }, { label: "信号故障", path: "/fault" }, { label: "检修工具", path: "/tool" }, { label: "技术规章", path: "/regulation" }, { label: "技能培训", path: "/training" }]

function switchRole(role: string) {
  store.switchRole(role)
  window.location.reload()
}

onMounted(async () => {
  try {
    const response = await request('/api/transformation/roles')
    if (!response.ok) throw new Error(await readActionError(response, '岗位配置读取失败'))
    const payload = (await response.json()) as { items: RolePreset[] }
    store.setRolePresets(payload.items)
  } catch {
    // 保留前端内置岗位，避免后端暂时不可用时页面无法切换。
  }
})
</script>

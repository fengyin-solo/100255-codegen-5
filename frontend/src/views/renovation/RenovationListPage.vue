<template>
  <section class="page" data-module="renovation">
    <header class="page-head">
      <div>
        <h2>{{ title }}</h2>
        <p class="page-desc">{{ desc }}</p>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span><strong>{{ card.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>项目编号/名称</span>
        <input v-model="keyword" placeholder="按编号或名称检索" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="status">
          <option value="">本页关注状态</option>
          <option v-for="item in options" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetAll">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>项目编号</th>
          <th>项目名称</th>
          <th>责任部门</th>
          <th>责任人</th>
          <th>立项人</th>
          <th>预算(万元)</th>
          <th>状态</th>
          <th v-if="mode === 'proposal'">退回理由</th>
          <th v-else>验收结论</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id" :class="{ 'row-locked': row.权限['已投运只读'] }">
          <td>{{ row.项目编号 }}</td>
          <td>{{ row.项目名称 }}</td>
          <td>{{ row.责任部门 }}</td>
          <td>{{ row.责任人 }}</td>
          <td>{{ row.立项人 }}</td>
          <td>{{ row.预算金额 ?? '—' }}</td>
          <td><span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span></td>
          <td class="cell-note">
            <template v-if="mode === 'proposal'">{{ row.退回理由 || '—' }}</template>
            <template v-else>{{ row.验收结论 || '待验收' }}</template>
          </td>
          <td><button class="link" type="button" @click="activeId = row.id">查看/办理</button></td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="9" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条记录 · 负责人字段与项目台账同源，三处页面始终是同一个人</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
    </footer>

    <ProjectDrawer :project-id="activeId" @close="activeId = null" @changed="onChanged" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { renovationApi, type ProjectRow } from '@/api/renovation'
import { useSessionStore } from '@/stores/session'
import ProjectDrawer from './ProjectDrawer.vue'

const props = defineProps<{
  mode: 'proposal' | 'acceptance'
  title: string
  desc: string
  emptyText: string
  options: string[]
}>()

const session = useSessionStore()
const rows = ref<ProjectRow[]>([])
const total = ref(0)
const keyword = ref('')
const status = ref('')
const activeId = ref<number | null>(null)
const message = ref('')
const messageOk = ref(false)

const cards = computed(() => {
  if (props.mode === 'proposal') {
    return [
      { label: '编制中', value: rows.value.filter((r) => r.status === '编制中').length },
      { label: '待审核', value: rows.value.filter((r) => r.status === '待审核').length },
      { label: '已退回待修改', value: rows.value.filter((r) => r.status === '已退回').length },
    ]
  }
  return [
    { label: '待验收', value: rows.value.filter((r) => r.status === '待验收').length },
    { label: '已投运', value: rows.value.filter((r) => r.status === '已投运').length },
    { label: '实施中', value: rows.value.filter((r) => r.status === '实施中').length },
  ]
})

function statusClass(s: string) {
  if (s === '已投运') return 'st-running'
  if (s === '已退回') return 'st-rejected'
  if (s === '待审核' || s === '待验收') return 'st-wait'
  return 'st-normal'
}

function resetAll() {
  keyword.value = ''
  status.value = ''
  void reload()
}

function onChanged() {
  message.value = '操作已生效'
  messageOk.value = true
  void reload()
}

async function reload() {
  message.value = ''
  const params: Record<string, string> = { size: '100' }
  if (keyword.value.trim()) params.keyword = keyword.value.trim()
  if (status.value) params.status = status.value
  try {
    const payload = await renovationApi.list(params)
    // 本页只关注立项环节 / 验收环节的状态；未选具体状态时在前端再收窄一次
    rows.value = payload.items.filter((row) => props.options.includes(row.status))
    total.value = rows.value.length
  } catch (error) {
    message.value = error instanceof Error ? error.message : '列表读取失败'
    messageOk.value = false
  }
}

watch(() => session.currentUserId, () => void reload())
onMounted(reload)
</script>

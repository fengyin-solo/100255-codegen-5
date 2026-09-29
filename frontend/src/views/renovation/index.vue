<template>
  <section class="page" data-module="renovation">
    <header class="page-head">
      <div>
        <h2>技术改造项目台账</h2>
        <p class="page-desc">
          立项 → 审核 → 实施 → 投运验收的归属与权限台账。负责人在台账、立项单、投运验收三处保持一致；
          已投运项目对所有岗位只读。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">登记改造项目</button>
      </div>
    </header>

    <form v-if="showCreate" class="filter-bar create-bar" @submit.prevent="submitCreate">
      <label class="filter-item">
        <span>项目名称（必填）</span>
        <input v-model="createForm.name" placeholder="如：车站信号机LED光源改造" />
      </label>
      <label class="filter-item">
        <span>预算金额（万元，可先空后补）</span>
        <input v-model.number="createForm.budget" type="number" step="0.1" min="0" />
      </label>
      <button class="btn primary" type="submit">提交立项</button>
      <p class="hint">立项后责任人默认为立项人本人；查看岗无立项权限，提交会被后端当场拦下。</p>
    </form>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">可见项目总数</span><strong>{{ total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待我处理</span><strong>{{ pendingCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已退回</span><strong>{{ rejectedCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已投运（只读）</span><strong>{{ runningCount }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>项目编号/名称</span>
        <input v-model="filters.keyword" placeholder="按编号或名称检索" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>项目编号</th>
          <th>项目名称</th>
          <th>责任部门</th>
          <th>责任人</th>
          <th>立项人</th>
          <th>跨部门共同责任人</th>
          <th>预算(万元)</th>
          <th>状态</th>
          <th>明细</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id" :class="{ 'row-locked': row.权限['已投运只读'], 'row-rejected': row.status === '已退回' }">
          <td>{{ row.项目编号 }}</td>
          <td>{{ row.项目名称 }}</td>
          <td>{{ row.责任部门 }}</td>
          <td>{{ row.责任人 }}</td>
          <td>{{ row.立项人 }}</td>
          <td>{{ row.共同责任人 }}</td>
          <td>{{ row.预算金额 ?? '—' }}</td>
          <td>
            <span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span>
            <span v-if="row.权限['已投运只读']" class="readonly-flag">只读</span>
          </td>
          <td><button class="link" type="button" @click="openDetail(row.id)">查看/办理</button></td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="9" class="empty-state">当前岗位暂无可查看的改造项目，或筛选条件无匹配</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条可见记录（仅显示本部门、本人或共享给本部门的项目）</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
    </footer>

    <ProjectDrawer :project-id="activeId" @close="activeId = null" @changed="onChanged" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { renovationApi, type ProjectRow } from '@/api/renovation'
import { useSessionStore } from '@/stores/session'
import ProjectDrawer from './ProjectDrawer.vue'

const session = useSessionStore()

const rows = ref<ProjectRow[]>([])
const total = ref(0)
const message = ref('')
const messageOk = ref(false)
const statuses = ref<string[]>([])
const activeId = ref<number | null>(null)
const showCreate = ref(false)
const createForm = reactive({ name: '', budget: null as number | null })
const filters = reactive({ keyword: '', status: '' })

const pendingCount = computed(() => rows.value.filter((r) => r.pending).length)
const rejectedCount = computed(() => rows.value.filter((r) => r.status === '已退回').length)
const runningCount = computed(() => rows.value.filter((r) => r.status === '已投运').length)

function statusClass(status: string) {
  if (status === '已投运') return 'st-running'
  if (status === '已退回') return 'st-rejected'
  if (status === '待审核' || status === '待验收') return 'st-wait'
  return 'st-normal'
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function openDetail(id: number) {
  activeId.value = id
}

function onChanged() {
  message.value = '操作已生效，台账已刷新'
  messageOk.value = true
  void reload()
}

async function submitCreate() {
  message.value = ''
  if (!createForm.name.trim()) {
    message.value = '项目名称为必填项'
    messageOk.value = false
    return
  }
  try {
    const result = await renovationApi.create({
      项目名称: createForm.name.trim(),
      预算金额: createForm.budget,
    })
    message.value = result.message
    messageOk.value = true
    showCreate.value = false
    createForm.name = ''
    createForm.budget = null
    await reload()
    activeId.value = result.entry.id
  } catch (error) {
    message.value = error instanceof Error ? error.message : '立项失败'
    messageOk.value = false
  }
}

async function reload() {
  message.value = ''
  const params: Record<string, string> = {}
  if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
  if (filters.status) params.status = filters.status
  try {
    const payload = await renovationApi.list(params)
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    message.value = error instanceof Error ? error.message : '台账读取失败'
    messageOk.value = false
  }
}

watch(() => session.currentUserId, () => void reload())

onMounted(async () => {
  try {
    const meta = await renovationApi.meta()
    statuses.value = meta.statuses
  } catch {
    statuses.value = []
  }
  await reload()
})
</script>

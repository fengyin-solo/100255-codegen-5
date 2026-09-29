<template>
  <div v-if="open" class="drawer-mask" @click.self="close">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <h3>{{ entry?.项目名称 ?? '改造项目明细' }}</h3>
          <p class="page-desc">{{ entry?.项目编号 }} · {{ entry?.责任部门 }}</p>
        </div>
        <button class="btn ghost" type="button" @click="close">关闭</button>
      </header>

      <div v-if="loading" class="drawer-body">明细加载中…</div>
      <div v-else-if="entry" class="drawer-body">
        <!-- 三处页面同源的负责人字段：台账/立项单/验收页都显示这一个责任人 -->
        <section class="detail-grid">
          <div><span class="stat-label">责任人（台账/立项单/验收页一致）</span><strong>{{ entry.责任人 }}</strong></div>
          <div><span class="stat-label">责任部门</span><strong>{{ entry.责任部门 }}</strong></div>
          <div><span class="stat-label">立项人</span><strong>{{ entry.立项人 }}</strong></div>
          <div><span class="stat-label">跨部门共同责任人</span><strong>{{ entry.共同责任人 }}</strong></div>
          <div><span class="stat-label">预算金额（万元）</span><strong>{{ entry.预算金额 ?? '—' }}</strong></div>
          <div><span class="stat-label">当前状态</span><strong>{{ entry.status }}</strong></div>
        </section>

        <section v-if="entry.退回理由" class="notice reject">
          <strong>审核退回理由：</strong>{{ entry.退回理由 }}
        </section>
        <section v-if="entry.验收结论" class="notice accept">
          <strong>投运验收结论：</strong>{{ entry.验收结论 }}
        </section>
        <section v-if="entry.权限['已投运只读']" class="notice locked">
          该改造项目已投运验收，当前岗位仅可查看，任何改动（预算、验收结论、责任人）都会被后端拦截。
        </section>

        <!-- 可执行动作：由后端下发的 entry.权限 决定，越权按钮直接不出现 -->
        <section class="action-panel">
          <h4>本岗位可办动作</h4>
          <div v-if="availableActions.length === 0" class="muted">当前岗位在该项目当前环节没有可执行动作，仅可查看。</div>
          <div class="action-grid">
            <template v-for="item in availableActions" :key="item.key">
              <button
                v-if="item.key !== '审核退回' && item.key !== '投运验收'"
                class="btn"
                type="button"
                @click="runSimple(item.action)"
              >{{ item.key }}</button>
            </template>
            <button v-if="entry.权限['审核退回']" class="btn" type="button" @click="openPrompt('审核退回')">审核退回（须写理由）</button>
            <button v-if="entry.权限['投运验收']" class="btn primary" type="button" @click="openPrompt('投运验收')">填写验收结论并投运</button>
            <button v-if="entry.权限['修改立项单'] || entry.权限['修改预算']" class="btn" type="button" @click="editing = !editing">
              {{ editing ? '收起编辑' : '修改立项单/预算' }}
            </button>
            <button v-if="entry.权限['移交责任人']" class="btn" type="button" @click="showTransfer = !showTransfer">
              {{ showTransfer ? '收起移交' : '移交责任人' }}
            </button>
            <button v-if="entry.权限['指定共同责任人']" class="btn" type="button" @click="showCoOwner = !showCoOwner">
              {{ showCoOwner ? '收起共享' : '指定跨部门共同责任人' }}
            </button>
          </div>

          <!-- 退回理由 / 验收结论 -->
          <form v-if="promptMode" class="inline-form" @submit.prevent="submitPrompt">
            <label class="filter-item">
              <span>{{ promptMode === '审核退回' ? '退回理由（必填）' : '投运验收结论（必填）' }}</span>
              <textarea v-model="promptText" rows="3" :placeholder="promptMode === '审核退回' ? '请写明退回理由，立项人将据此修改' : '请填写投运验收结论'"></textarea>
            </label>
            <button class="btn primary" type="submit">确认{{ promptMode }}</button>
          </form>

          <!-- 修改立项单 -->
          <form v-if="editing" class="inline-form" @submit.prevent="submitPatch">
            <label v-if="entry.权限['修改立项单']" class="filter-item">
              <span>项目名称</span>
              <input v-model="patchName" />
            </label>
            <label v-if="entry.权限['修改预算']" class="filter-item">
              <span>预算金额（万元）</span>
              <input v-model.number="patchBudget" type="number" step="0.1" min="0" />
            </label>
            <button class="btn primary" type="submit">保存修改</button>
          </form>

          <!-- 移交责任人：记录写入后端，刷新仍在 -->
          <form v-if="showTransfer" class="inline-form" @submit.prevent="submitTransfer">
            <label class="filter-item">
              <span>移交给谁</span>
              <select v-model="transferUserId">
                <option value="" disabled>请选择新责任人</option>
                <option v-for="u in candidateTransferees" :key="u.id" :value="u.id">
                  {{ u.name }}｜{{ u.role }}｜{{ u.department }}
                </option>
              </select>
            </label>
            <label class="filter-item">
              <span>移交原因</span>
              <input v-model="transferReason" placeholder="如：工作调整/车间承接" />
            </label>
            <button class="btn primary" type="submit">确认移交并留痕</button>
            <p class="hint">同一部门内只能保留一个责任人；跨部门移交后责任部门随新责任人变更。</p>
          </form>

          <!-- 跨部门共同责任人 -->
          <form v-if="showCoOwner" class="inline-form" @submit.prevent="submitCoOwner">
            <label class="filter-item">
              <span>共同责任人（须为其他部门）</span>
              <select v-model="coOwnerUserId">
                <option value="" disabled>请选择跨部门人员</option>
                <option v-for="u in candidateCoOwners" :key="u.id" :value="u.id">
                  {{ u.name }}｜{{ u.role }}｜{{ u.department }}
                </option>
              </select>
            </label>
            <button class="btn primary" type="submit">确认共享查看</button>
          </form>
        </section>

        <!-- 移交记录：刷新页面后重新从后端拉取，历史不丢 -->
        <section class="log-panel">
          <h4>责任人移交记录</h4>
          <table v-if="transferLogs.length" class="data-table compact">
            <thead>
              <tr><th>时间</th><th>原责任人（部门）</th><th>新责任人（部门）</th><th>移交人</th><th>原因</th></tr>
            </thead>
            <tbody>
              <tr v-for="log in transferLogs" :key="log.id">
                <td>{{ log.时间 }}</td>
                <td>{{ log.原责任人 }}（{{ log.原责任部门 }}）</td>
                <td>{{ log.新责任人 }}（{{ log.新责任部门 }}）</td>
                <td>{{ log.移交人 }}</td>
                <td>{{ log.移交原因 }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="muted">暂无移交记录，责任人自立项以来未变更。</p>
        </section>

        <section class="log-panel">
          <h4>流转记录</h4>
          <ul class="timeline">
            <li v-for="(log, idx) in entry.流转记录" :key="idx">
              <span class="timeline-time">{{ log.时间 }}</span>
              <span class="timeline-action">{{ log.动作 }}</span>
              <span class="muted">{{ log.操作人 }}（{{ log.岗位 }}）：{{ log.说明 }}</span>
            </li>
          </ul>
        </section>
      </div>

      <p v-if="errorMessage" class="drawer-error">{{ errorMessage }}</p>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { renovationApi, type ProjectRow, type TransferLog } from '@/api/renovation'
import { useSessionStore } from '@/stores/session'

const props = defineProps<{ projectId: number | null }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const session = useSessionStore()

const open = computed(() => props.projectId !== null)
const loading = ref(false)
const entry = ref<ProjectRow | null>(null)
const transferLogs = ref<TransferLog[]>([])
const errorMessage = ref('')

const editing = ref(false)
const patchName = ref('')
const patchBudget = ref<number | null>(null)
const showTransfer = ref(false)
const transferUserId = ref('')
const transferReason = ref('')
const showCoOwner = ref(false)
const coOwnerUserId = ref('')
const promptMode = ref<'' | '审核退回' | '投运验收'>('')
const promptText = ref('')

const SIMPLE_ACTIONS: { key: string; action: string }[] = [
  { key: '提交审核', action: '提交审核' },
  { key: '审核通过', action: '审核通过' },
  { key: '重新提交', action: '重新提交' },
  { key: '安排实施', action: '安排实施' },
  { key: '实施报竣', action: '实施报竣' },
]

const availableActions = computed(() =>
  SIMPLE_ACTIONS.filter((item) => entry.value?.权限[item.key]),
)

const candidateTransferees = computed(() =>
  session.users.filter((u) => u.id !== entry.value?.责任人),
)

const candidateCoOwners = computed(() => {
  const existingIds = new Set((entry.value?.共同责任人明细 ?? []).map((u) => u.id))
  return session.users.filter(
    (u) => u.department !== entry.value?.责任部门 && !existingIds.has(u.id) && u.name !== entry.value?.责任人,
  )
})

function close() {
  emit('close')
}

function resetForms() {
  editing.value = false
  showTransfer.value = false
  showCoOwner.value = false
  promptMode.value = ''
  promptText.value = ''
  transferUserId.value = ''
  transferReason.value = ''
  coOwnerUserId.value = ''
}

async function load() {
  if (props.projectId === null) return
  loading.value = true
  errorMessage.value = ''
  try {
    const detail = await renovationApi.detail(props.projectId)
    entry.value = detail.entry
    transferLogs.value = detail.transfer_logs
    patchName.value = detail.entry.项目名称
    patchBudget.value = detail.entry.预算金额
    resetForms()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '明细读取失败'
  } finally {
    loading.value = false
  }
}

function reportError(error: unknown) {
  errorMessage.value = error instanceof Error ? error.message : '操作未生效'
}

async function runSimple(action: string) {
  if (!entry.value) return
  errorMessage.value = ''
  try {
    const result = await renovationApi.action(entry.value.id, { action })
    entry.value = result.entry
    emit('changed')
    await load()
  } catch (error) {
    reportError(error)
  }
}

function openPrompt(mode: '审核退回' | '投运验收') {
  promptMode.value = mode
  promptText.value = ''
}

async function submitPrompt() {
  if (!entry.value || !promptMode.value) return
  if (!promptText.value.trim()) {
    errorMessage.value = promptMode.value === '审核退回' ? '退回必须写明理由' : '投运验收必须填写结论'
    return
  }
  errorMessage.value = ''
  try {
    const payload =
      promptMode.value === '审核退回'
        ? { action: '审核退回', reason: promptText.value }
        : { action: '投运验收', conclusion: promptText.value }
    const result = await renovationApi.action(entry.value.id, payload)
    entry.value = result.entry
    promptMode.value = ''
    emit('changed')
    await load()
  } catch (error) {
    reportError(error)
  }
}

async function submitPatch() {
  if (!entry.value) return
  errorMessage.value = ''
  const payload: { 项目名称?: string; 预算金额?: number | null } = {}
  if (entry.value.权限['修改立项单'] && patchName.value.trim()) {
    payload.项目名称 = patchName.value.trim()
  }
  if (entry.value.权限['修改预算'] && patchBudget.value !== null) {
    payload.预算金额 = patchBudget.value
  }
  try {
    const result = await renovationApi.patch(entry.value.id, payload)
    entry.value = result.entry
    editing.value = false
    emit('changed')
    await load()
  } catch (error) {
    reportError(error)
  }
}

async function submitTransfer() {
  if (!entry.value) return
  if (!transferUserId.value) {
    errorMessage.value = '请选择新责任人'
    return
  }
  errorMessage.value = ''
  try {
    const result = await renovationApi.transfer(entry.value.id, {
      to_user_id: transferUserId.value,
      reason: transferReason.value,
    })
    entry.value = result.entry
    showTransfer.value = false
    emit('changed')
    await load()
  } catch (error) {
    reportError(error)
  }
}

async function submitCoOwner() {
  if (!entry.value) return
  if (!coOwnerUserId.value) {
    errorMessage.value = '请选择跨部门共同责任人'
    return
  }
  errorMessage.value = ''
  try {
    const result = await renovationApi.addCoOwner(entry.value.id, coOwnerUserId.value)
    entry.value = result.entry
    showCoOwner.value = false
    emit('changed')
    await load()
  } catch (error) {
    reportError(error)
  }
}

watch(
  () => props.projectId,
  (id) => {
    if (id !== null) void load()
  },
  { immediate: true },
)

// 顶栏切换岗位后，权限变了，抽屉内容要按新岗位重算
watch(
  () => session.currentUserId,
  () => {
    if (props.projectId !== null) void load()
  },
)
</script>

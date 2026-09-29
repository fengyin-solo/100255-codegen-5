<template>
  <section class="page transformation-page" data-module="transformation">
    <header class="page-head">
      <div>
        <h2>技术改造项目</h2>
        <p class="page-desc">覆盖立项、审核、实施、完工、投运验收与责任移交；预算、验收结论和责任人归属由后端强制校验。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">新建立项单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="tab-bar" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="keyword" placeholder="项目编号 / 名称 / 负责人" />
      </label>
      <label class="filter-item">
        <span>项目状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table v-if="activeTab === 'ledger'" class="data-table">
      <thead>
        <tr>
          <th v-for="column in ledgerColumns" :key="column">{{ column }}</th>
          <th>权限提示</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in ledgerColumns" :key="column">{{ formatCell(row, column) }}</td>
          <td>{{ permissionHint(row) }}</td>
          <td class="row-actions action-stack">
            <button v-if="canEdit(row)" class="link" type="button" @click="openEdit(row)">编辑预算/内容</button>
            <button v-if="canSubmit(row)" class="link" type="button" @click="runAction('提交审核', row)">提交审核</button>
            <button v-if="canReview(row)" class="link" type="button" @click="openReject(row)">退回</button>
            <button v-if="canReview(row)" class="link" type="button" @click="runAction('审核通过', row)">审核通过</button>
            <button v-if="canImplement(row)" class="link" type="button" @click="runAction('开始实施', row)">开始实施</button>
            <button v-if="canComplete(row)" class="link" type="button" @click="runAction('完工填报', row)">完工填报</button>
            <button v-if="canAccept(row)" class="link" type="button" @click="openAcceptance(row)">投运验收</button>
            <button v-if="canTransfer(row)" class="link" type="button" @click="openTransfer(row)">移交责任人</button>
            <button class="link" type="button" @click="showHistory(row)">移交记录</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="ledgerColumns.length + 2" class="empty-state">当前岗位暂无可查看的技术改造项目</td>
        </tr>
      </tbody>
    </table>

    <table v-else-if="activeTab === 'proposal'" class="data-table">
      <thead>
        <tr><th v-for="column in proposalColumns" :key="column">{{ column }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in proposalRows" :key="String(row.id)">
          <td v-for="column in proposalColumns" :key="column">{{ row[column] ?? '—' }}</td>
        </tr>
        <tr v-if="!proposalRows.length"><td :colspan="proposalColumns.length" class="empty-state">暂无立项单</td></tr>
      </tbody>
    </table>

    <table v-else class="data-table">
      <thead>
        <tr><th v-for="column in acceptanceColumns" :key="column">{{ column }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in acceptanceRows" :key="String(row.id)">
          <td v-for="column in acceptanceColumns" :key="column">{{ formatCell(row, column) }}</td>
        </tr>
        <tr v-if="!acceptanceRows.length"><td :colspan="acceptanceColumns.length" class="empty-state">暂无投运验收页</td></tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条记录 · 当前岗位：{{ store.role }} / {{ store.department }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
    </footer>

    <div v-if="modal.open" class="modal-mask" @click.self="closeModal">
      <form class="modal-card" @submit.prevent="submitModal">
        <h3>{{ modal.title }}</h3>

        <template v-if="modal.mode === 'create'">
          <label v-for="field in createFields" :key="field.name" class="modal-field">
            <span>{{ field.label }}<em v-if="field.required">*</em></span>
            <input v-model="formValues[field.name]" :placeholder="field.placeholder" />
          </label>
        </template>

        <template v-else-if="modal.mode === 'edit'">
          <label class="modal-field">
            <span>预算金额（元）</span>
            <input v-model="formValues['预算金额']" type="number" min="0" />
          </label>
          <label class="modal-field">
            <span>项目名称</span>
            <input v-model="formValues['项目名称']" />
          </label>
          <label class="modal-field">
            <span>改造内容</span>
            <textarea v-model="formValues['改造内容']" rows="4" />
          </label>
          <label class="modal-field">
            <span>计划完成日期</span>
            <input v-model="formValues['计划完成日期']" type="date" />
          </label>
        </template>

        <template v-else-if="modal.mode === 'reject'">
          <label class="modal-field">
            <span>退回理由<em>*</em></span>
            <textarea v-model="formValues.reason" rows="4" placeholder="请写明预算、方案或材料缺失的具体原因" />
          </label>
        </template>

        <template v-else-if="modal.mode === 'acceptance'">
          <label class="modal-field">
            <span>验收结论<em>*</em></span>
            <textarea v-model="formValues['验收结论']" rows="4" placeholder="例如：联锁试验合格，同意投运" />
          </label>
          <label class="modal-field">
            <span>投运日期<em>*</em></span>
            <input v-model="formValues['投运日期']" type="date" />
          </label>
        </template>

        <template v-else-if="modal.mode === 'transfer'">
          <label class="modal-field">
            <span>新负责人<em>*</em></span>
            <input v-model="formValues.to" placeholder="例如：孙九" />
          </label>
          <label class="modal-field">
            <span>新责任部门<em>*</em></span>
            <input v-model="formValues.to_department" placeholder="同部门替换；跨部门自动保留共同查看" />
          </label>
          <label class="modal-field">
            <span>移交原因<em>*</em></span>
            <textarea v-model="formValues.reason" rows="3" />
          </label>
          <p class="modal-tip">同一部门内只能有一名责任人；跨部门移交会把原负责人追加为共同责任人。</p>
        </template>

        <template v-else-if="modal.mode === 'history'">
          <ol class="history-list">
            <li v-for="(item, index) in historyRecords" :key="index">
              <strong>{{ item.time }}</strong>
              <span>{{ item.from || '建档' }}（{{ item.from_department || '—' }}）→ {{ item.to }}（{{ item.to_department }}）</span>
              <em>{{ item.reason }}</em>
            </li>
          </ol>
        </template>

        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeModal">{{ modal.mode === 'history' ? '关闭' : '取消' }}</button>
          <button v-if="modal.mode !== 'history'" class="btn primary" type="submit">确认</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { readActionError, request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type CoOwner = { name: string; department: string }
type Row = Record<string, string | number | boolean | null | CoOwner[] | Permissions>
type Permissions = {
  可查看: boolean
  可编辑: boolean
  可审核: boolean
  可验收: boolean
  可移交: boolean
}
type ActionResponse = { ok: boolean; message: string; entry?: Row }

const store = useSessionStore()
const ENDPOINT = '/api/transformation'

const tabs = [
  { key: 'ledger', label: '项目台账' },
  { key: 'proposal', label: '立项单' },
  { key: 'acceptance', label: '投运验收页' },
] as const

const statuses = ['待提交', '待审核', '已退回', '审核通过', '实施中', '完工待验', '已投运']
const ledgerColumns = ['项目编号', '项目名称', '责任部门', '负责人', '共同责任人', '立项人', '预算金额', 'status', '验收结论']
const proposalColumns = ['项目编号', '项目名称', '责任部门', '负责人', '立项人', '立项部门', '预算金额', '计划完成日期', '项目状态', '退回理由']
const acceptanceColumns = ['项目编号', '项目名称', '责任部门', '负责人', '共同责任人', '项目状态', '验收结论', '投运日期']
const createFields = [
  { name: '项目编号', label: '项目编号', required: true, placeholder: 'JG-2026-004' },
  { name: '项目名称', label: '项目名称', required: true, placeholder: '技术改造项目名称' },
  { name: '预算金额', label: '预算金额（元）', required: true, placeholder: '0' },
  { name: '改造内容', label: '改造内容', required: false, placeholder: '改造范围与目标' },
  { name: '计划完成日期', label: '计划完成日期', required: false, placeholder: 'YYYY-MM-DD' },
]

const activeTab = ref<(typeof tabs)[number]['key']>('ledger')
const rows = ref<Row[]>([])
const proposalRows = ref<Row[]>([])
const acceptanceRows = ref<Row[]>([])
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')
const selectedId = ref<number | null>(null)
const historyRecords = ref<Record<string, string>[]>([])
const formValues = reactive<Record<string, string>>({})
const modal = reactive<{ open: boolean; mode: 'create' | 'edit' | 'reject' | 'acceptance' | 'transfer' | 'history'; title: string }>({
  open: false,
  mode: 'create',
  title: '',
})

const stats = computed(() => [
  { label: '可见项目', value: total.value },
  { label: '待审核', value: rows.value.filter((row) => row.status === '待审核').length },
  { label: '实施/待验', value: rows.value.filter((row) => ['实施中', '完工待验'].includes(String(row.status))).length },
  { label: '已投运', value: rows.value.filter((row) => row.status === '已投运').length },
])

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function permissions(row: Row): Permissions {
  return (row['当前用户权限'] as Permissions) ?? { 可查看: false, 可编辑: false, 可审核: false, 可验收: false, 可移交: false }
}

function canEdit(row: Row) {
  return permissions(row).可编辑
}
function canSubmit(row: Row) {
  return canEdit(row) && ['待提交', '已退回'].includes(String(row.status))
}
function canReview(row: Row) {
  return permissions(row).可审核
}
function canImplement(row: Row) {
  return store.permissions.includes('技术改造实施') && ['审核通过', '实施中'].includes(String(row.status))
}
function canComplete(row: Row) {
  return store.permissions.includes('技术改造实施') && row.status === '实施中'
}
function canAccept(row: Row) {
  return permissions(row).可验收
}
function canTransfer(row: Row) {
  return permissions(row).可移交
}

function permissionHint(row: Row) {
  const p = permissions(row)
  if (row.status === '已投运') return '已投运：仅查看和责任移交'
  if (p.可编辑) return '当前负责人：可修改并提交'
  if (p.可审核) return '审核岗：可通过或退回'
  if (p.可验收) return '验收岗：可填写验收结论'
  return '共享查看：不可改动'
}

function formatCell(row: Row, column: string) {
  const value = row[column]
  if (column === '共同责任人' && Array.isArray(value)) {
    return value.length ? value.map((item) => `${item.name}（${item.department}）`).join('、') : '—'
  }
  if (column === '预算金额' && typeof value === 'number') return `¥${value.toLocaleString('zh-CN')}`
  return value === '' || value === null || value === undefined ? '—' : String(value)
}

function openCreate() {
  Object.keys(formValues).forEach((key) => delete formValues[key])
  showModal('create', '新建立项单')
}

function openEdit(row: Row) {
  selectedId.value = Number(row.id)
  Object.keys(formValues).forEach((key) => delete formValues[key])
  formValues['项目名称'] = String(row['项目名称'] ?? '')
  formValues['预算金额'] = String(row['预算金额'] ?? '')
  formValues['改造内容'] = String(row['改造内容'] ?? '')
  formValues['计划完成日期'] = String(row['计划完成日期'] ?? '')
  showModal('edit', '编辑技术改造项目')
}

function openReject(row: Row) {
  selectedId.value = Number(row.id)
  Object.keys(formValues).forEach((key) => delete formValues[key])
  showModal('reject', '退回技术改造项目')
}

function openAcceptance(row: Row) {
  selectedId.value = Number(row.id)
  Object.keys(formValues).forEach((key) => delete formValues[key])
  formValues['投运日期'] = new Date().toISOString().slice(0, 10)
  showModal('acceptance', '投运验收')
}

function openTransfer(row: Row) {
  selectedId.value = Number(row.id)
  Object.keys(formValues).forEach((key) => delete formValues[key])
  formValues.to_department = String(row['责任部门'] ?? '')
  showModal('transfer', '移交责任人')
}

function showHistory(row: Row) {
  selectedId.value = Number(row.id)
  historyRecords.value = (row['移交记录'] as Record<string, string>[] | undefined) ?? []
  showModal('history', '责任移交记录')
}

function showModal(mode: typeof modal.mode, title: string) {
  modal.mode = mode
  modal.title = title
  modal.open = true
  errorMessage.value = ''
  noticeMessage.value = ''
}

function closeModal() {
  modal.open = false
}

async function submitModal() {
  if (modal.mode === 'create') await createEntry()
  else if (modal.mode === 'edit') await patchEntry()
  else if (modal.mode === 'reject') await runAction('退回')
  else if (modal.mode === 'acceptance') await runAction('投运验收')
  else if (modal.mode === 'transfer') await transferOwner()
}

async function postJson(path: string, body: Record<string, unknown>) {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  if (!response.ok) throw new Error(await readActionError(response, '操作未生效'))
  return (await response.json()) as ActionResponse
}

async function createEntry() {
  try {
    const values: Record<string, unknown> = { ...formValues }
    if (values['预算金额']) values['预算金额'] = Number(values['预算金额'])
    const payload = await postJson(ENDPOINT, { values })
    if (!payload.ok) throw new Error(payload.message)
    noticeMessage.value = payload.message
    closeModal()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '立项失败'
  }
}

async function patchEntry() {
  if (selectedId.value === null) return
  try {
    const values = {
      项目名称: formValues['项目名称'],
      预算金额: Number(formValues['预算金额']),
      改造内容: formValues['改造内容'],
      计划完成日期: formValues['计划完成日期'],
    }
    const response = await request(`${ENDPOINT}/${selectedId.value}`, {
      method: 'PATCH',
      body: JSON.stringify({ values }),
    })
    if (!response.ok) throw new Error(await readActionError(response, '修改未生效'))
    const payload = (await response.json()) as ActionResponse
    noticeMessage.value = payload.message
    closeModal()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '修改失败'
  }
}

async function runAction(action: string, row?: Row) {
  const id = row ? Number(row.id) : selectedId.value
  if (id === null || id === undefined) return
  try {
    const values: Record<string, unknown> = { action }
    if (modal.mode === 'reject') values.reason = formValues.reason
    if (modal.mode === 'acceptance') {
      values['验收结论'] = formValues['验收结论']
      values['投运日期'] = formValues['投运日期']
    }
    const payload = await postJson(`${ENDPOINT}/${id}/actions`, { values })
    noticeMessage.value = payload.message
    closeModal()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '动作执行失败'
  }
}

async function transferOwner() {
  if (selectedId.value === null) return
  try {
    const payload = await postJson(`${ENDPOINT}/${selectedId.value}/transfer`, { values: { ...formValues } })
    noticeMessage.value = payload.message
    closeModal()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '责任移交失败'
  }
}

async function reload() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  try {
    const [ledgerResponse, proposalResponse, acceptanceResponse] = await Promise.all([
      request(`${ENDPOINT}${suffix}`),
      request(`${ENDPOINT}/proposal${suffix}`),
      request(`${ENDPOINT}/acceptance${suffix}`),
    ])
    if (!ledgerResponse.ok || !proposalResponse.ok || !acceptanceResponse.ok) {
      throw new Error('技术改造项目数据读取失败')
    }
    const ledgerPayload = await ledgerResponse.json()
    const proposalPayload = await proposalResponse.json()
    const acceptancePayload = await acceptanceResponse.json()
    rows.value = ledgerPayload.items ?? []
    total.value = ledgerPayload.total ?? rows.value.length
    proposalRows.value = proposalPayload.items ?? []
    acceptanceRows.value = acceptancePayload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '技术改造项目数据读取失败'
  }
}

onMounted(reload)
</script>

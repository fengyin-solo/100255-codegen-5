import { defineStore } from 'pinia'

export type RolePreset = {
  name: string
  role: string
  department: string
  permissions: string[]
}

export const FALLBACK_ROLES: RolePreset[] = [
  { name: '张三', role: '立项人', department: '技术科', permissions: ['技术改造立项', '技术改造编辑', '技术改造提交', '技术改造责任移交'] },
  { name: '李四', role: '审核岗', department: '技术科', permissions: ['技术改造审核', '技术改造全局查看'] },
  { name: '王五', role: '实施岗', department: '施工科', permissions: ['技术改造实施', '技术改造全局查看', '技术改造责任移交'] },
  { name: '赵六', role: '验收岗', department: '技术科', permissions: ['技术改造验收', '技术改造全局查看'] },
  { name: '钱七', role: '查看岗', department: '安全科', permissions: [] },
]

const STORAGE_KEY = 'rail-signal-transformation-session'

function loadSession(): RolePreset {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<RolePreset>
      const matched = FALLBACK_ROLES.find((item) => item.role === parsed.role) ?? FALLBACK_ROLES[0]
      return { ...matched, ...parsed, permissions: parsed.permissions ?? matched.permissions }
    }
  } catch {
    // 本地会话损坏时回到默认立项人，不影响页面打开。
  }
  return { ...FALLBACK_ROLES[0] }
}

export const useSessionStore = defineStore('session', {
  state: () => {
    const current = loadSession()
    return {
      operator: current.name,
      shiftLabel: '白班 08:00-20:00',
      scope: '轨道交通信号检修管理平台',
      role: current.role,
      department: current.department,
      permissions: current.permissions,
      rolePresets: FALLBACK_ROLES,
    }
  },
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRolePresets(roles: RolePreset[]) {
      if (roles.length) {
        this.rolePresets = roles
      }
    },
    switchRole(role: string) {
      const preset = this.rolePresets.find((item) => item.role === role)
      if (!preset) return
      this.operator = preset.name
      this.role = preset.role
      this.department = preset.department
      this.permissions = [...preset.permissions]
      localStorage.setItem(STORAGE_KEY, JSON.stringify(preset))
    },
  },
})

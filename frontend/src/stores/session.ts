import { defineStore } from 'pinia'

/** 当前在岗人员：技术改造模块的所有接口都带 X-Operator-Id，后端据此判权限。 */
export type StaffUser = {
  id: string
  name: string
  role: string
  department: string
  permissions: string[]
}

type SessionState = {
  operator: string
  shiftLabel: string
  scope: string
  /** 在岗人员花名册，来自后端 /api/renovation/meta */
  users: StaffUser[]
  currentUserId: string
  loaded: boolean
}

const STORAGE_KEY = 'renovation.operatorId'

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '轨道交通信号检修管理平台',
    users: [],
    currentUserId: localStorage.getItem(STORAGE_KEY) || 'u_zhang',
    loaded: false,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    currentUser(state): StaffUser | undefined {
      return state.users.find((u) => u.id === state.currentUserId)
    },
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setUsers(users: StaffUser[]) {
      this.users = users
      this.loaded = true
      this.syncOperator()
    },
    switchUser(id: string) {
      this.currentUserId = id
      localStorage.setItem(STORAGE_KEY, id)
      this.syncOperator()
    },
    syncOperator() {
      const user = this.currentUser
      if (user) {
        this.operator = `${user.name}（${user.role}·${user.department}）`
      }
    },
  },
})

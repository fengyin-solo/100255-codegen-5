/** 统一请求封装：拼后端地址、带上当前岗位、把后端的可读错误透传给页面。 */
import { useSessionStore } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

/** 后端领域错误：消息可直接展示给操作人，requiredPermission 标明缺哪个权限。 */
export class ApiError extends Error {
  status: number
  requiredPermission?: string

  constructor(status: number, message: string, requiredPermission?: string) {
    super(message)
    this.status = status
    this.requiredPermission = requiredPermission
  }
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const session = useSessionStore()
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  if (session.currentUserId) {
    headers.set('X-Operator-Id', session.currentUserId)
  }
  return fetch(url, { ...init, headers }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

/** 供既有模块使用：非 2xx 时抛通用错误。 */
export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

/** 技术改造模块使用：解析 FastAPI 的 detail{message,required_permission}。 */
export async function parseActionError(response: Response): Promise<ApiError> {
  let message = `接口返回 ${response.status}，操作未生效`
  let requiredPermission: string | undefined
  try {
    const payload = await response.json()
    const detail = payload?.detail
    if (detail && typeof detail === 'object' && detail.message) {
      message = String(detail.message)
      requiredPermission = detail.required_permission
    } else if (typeof detail === 'string') {
      message = detail
    }
  } catch {
    /* 响应体不是 JSON 时保留默认消息 */
  }
  return new ApiError(response.status, message, requiredPermission)
}

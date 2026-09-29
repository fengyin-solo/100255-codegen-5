/** 技术改造项目接口封装。 */
import { ApiError, parseActionError, request } from '@/api/client'
import type { StaffUser } from '@/stores/session'

export type ProjectRow = {
  id: number
  项目编号: string
  项目名称: string
  责任部门: string
  责任人: string
  立项人: string
  共同责任人: string
  共同责任人明细: StaffUser[]
  预算金额: number | null
  status: string
  pending: boolean
  退回理由: string
  验收结论: string
  流转记录: { 时间: string; 操作人: string; 岗位: string; 动作: string; 说明: string }[]
  权限: Record<string, boolean>
}

export type ProjectDetail = {
  entry: ProjectRow
  transfer_logs: TransferLog[]
}

export type TransferLog = {
  id: number
  project_id: number
  项目编号: string
  时间: string
  移交人: string
  原责任人: string
  原责任部门: string
  新责任人: string
  新责任部门: string
  移交原因: string
}

export type Meta = {
  statuses: string[]
  users: StaffUser[]
  roles: { code: string; label: string }[]
  permission_labels: Record<string, string>
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await parseActionError(response)
  }
  return (await response.json()) as T
}

export const renovationApi = {
  meta: () => request('/api/renovation/meta').then((r) => unwrap<Meta>(r)),

  list: (params: Record<string, string> = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/api/renovation/projects?${query}`).then(
      (r) => unwrap<{ items: ProjectRow[]; total: number }>(r),
    )
  },

  detail: (id: number) =>
    request(`/api/renovation/projects/${id}`).then((r) => unwrap<ProjectDetail>(r)),

  create: (payload: { 项目名称: string; 预算金额?: number | null }) =>
    request('/api/renovation/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ ok: boolean; message: string; entry: ProjectRow }>(r)),

  patch: (id: number, payload: { 项目名称?: string; 预算金额?: number | null }) =>
    request(`/api/renovation/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ ok: boolean; message: string; entry: ProjectRow }>(r)),

  action: (
    id: number,
    payload: { action: string; reason?: string; conclusion?: string },
  ) =>
    request(`/api/renovation/projects/${id}/actions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ ok: boolean; message: string; entry: ProjectRow }>(r)),

  transfer: (id: number, payload: { to_user_id: string; reason?: string }) =>
    request(`/api/renovation/projects/${id}/transfer`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ ok: boolean; message: string; entry: ProjectRow }>(r)),

  addCoOwner: (id: number, userId: string) =>
    request(`/api/renovation/projects/${id}/co-owners`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }).then((r) => unwrap<{ ok: boolean; message: string; entry: ProjectRow }>(r)),

  transfers: (id: number) =>
    request(`/api/renovation/projects/${id}/transfers`).then(
      (r) => unwrap<{ items: TransferLog[] }>(r),
    ),
}

export { ApiError }

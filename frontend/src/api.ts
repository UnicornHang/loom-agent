export type User = { id: string; username: string; role: 'admin' | 'product_manager' | 'creator' | 'reviewer' | 'viewer'; is_active: boolean; created_at: string }
export type ProductGroup = { id: string; name: string; created_at: string }
export type Product = { id: string; group_id: string | null; sku: string; name: string; category: string; description: string; status: string; created_at: string }
export type Hotspot = { id: string; title: string; summary: string; content_type: 'text' | 'article' | 'video'; source_url: string | null; source_kind: string; industry: string; created_at: string }
export type Workflow = { id: string; hotspot_id: string; status: string; current_step: string; created_at: string }
export type AgentEvent = { id: string; sequence: number; agent_type: string; event_type: string; title: string; summary: string; created_at: string }

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

function csrfToken() {
  return document.cookie.split('; ').find(value => value.startsWith('loom_csrf='))?.slice('loom_csrf='.length) || ''
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = options?.method?.toUpperCase() || 'GET'
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && path !== '/auth/login') headers['X-CSRF-Token'] = csrfToken()
  const response = await fetch(`/api/v1${path}`, { credentials: 'same-origin', headers, ...options })
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') {
      window.dispatchEvent(new Event('loom:unauthorized'))
      if (window.location.pathname !== '/login') window.location.replace('/login')
    }
    const body = await response.json().catch(() => ({}))
    throw new ApiError(body.detail || `请求失败 (${response.status})`, response.status)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; mode: string }>('/health'),
  me: () => request<User>('/auth/me'),
  login: (username: string, password: string) => request<User>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
  changePassword: (current_password: string, new_password: string) => request<{ ok: boolean }>('/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password, new_password }) }),
  users: () => request<User[]>('/users'),
  createUser: (data: { username: string; password: string; role: User['role'] }) => request<User>('/users', { method: 'POST', body: JSON.stringify(data) }),
  setUserActive: (userId: string, is_active: boolean) => request<User>(`/users/${userId}/active`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  groups: () => request<ProductGroup[]>('/product-groups'),
  createGroup: (name: string) => request<ProductGroup>('/product-groups', { method: 'POST', body: JSON.stringify({ name }) }),
  grantGroup: (groupId: string, userId: string) => request<{ ok: boolean }>(`/product-groups/${groupId}/grants`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }),
  groupGrants: (groupId: string) => request<User[]>(`/product-groups/${groupId}/grants`),
  revokeGroup: (groupId: string, userId: string) => request<{ ok: boolean }>(`/product-groups/${groupId}/grants/${userId}`, { method: 'DELETE' }),
  products: () => request<Product[]>('/products'),
  createProduct: (data: { sku: string; name: string; category: string; description: string; group_id: string }) => request<Product>('/products', { method: 'POST', body: JSON.stringify(data) }),
  assignProductGroup: (productId: string, group_id: string) => request<Product>(`/products/${productId}/group`, { method: 'PATCH', body: JSON.stringify({ group_id }) }),
  hotspots: () => request<Hotspot[]>('/hotspots'),
  createHotspot: (data: { title: string; summary: string; content_type: Hotspot['content_type']; source_url: string | null; industry: string }) => request<Hotspot>('/hotspots', { method: 'POST', body: JSON.stringify(data) }),
  workflows: () => request<Workflow[]>('/workflows'),
  createWorkflow: (hotspot_id: string) => request<Workflow>('/workflows', { method: 'POST', body: JSON.stringify({ hotspot_id }) }),
  events: (id: string) => request<AgentEvent[]>(`/workflows/${id}/events`),
}


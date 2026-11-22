export type User = { id: string; username: string; role: 'admin' | 'product_manager' | 'creator' | 'reviewer' | 'viewer'; is_active: boolean; created_at: string }
export type ProductGroup = { id: string; name: string; created_at: string }
export type Product = { id: string; group_id: string | null; sku: string; name: string; category: string; description: string; status: string; created_at: string }
export type Hotspot = { id: string; title: string; summary: string; content_type: 'text' | 'article' | 'video'; source_url: string | null; source_kind: string; industry: string; created_at: string; source_metrics: { rank?: number; hot_value?: number; material_available?: boolean }; collected_at: string | null }
export type Workflow = { id: string; hotspot_id: string; status: string; current_step: string; created_at: string }
export type AgentEvent = { id: string; sequence: number; agent_type: string; event_type: string; title: string; summary: string; created_at: string }

export type ModelConnection = { id: string; name: string; base_url: string; model_name: string; enabled: boolean; created_at: string; options: { capability?: string; input_price?: number; output_price?: number; currency?: string } }
export type ModelConnectionInput = Omit<ModelConnection, 'id' | 'created_at'> & { api_key?: string }

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
    const detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map((item: { msg: string }) => item.msg).join('；') : undefined
    throw new ApiError(detail || `请求失败 (${response.status})`, response.status)
  }
  return response.json() as Promise<T>
}

export const api = {
  recommendationSettings: () => request<{ embedding_connection_id: string | null; per_call_budget: number }>('/recommendation-settings'),
  saveRecommendationSettings: (data: { embedding_connection_id: string | null; per_call_budget: number }) => request('/recommendation-settings', { method: 'PUT', body: JSON.stringify(data) }),
  indexProduct: (id: string) => request<{ cached: boolean; dimensions?: number }>(`/products/${id}/embedding`, { method: 'POST' }),
  recommendations: (id: string, revision: number, threshold: number) => request<{ items: Recommendation[]; notice: string }>(`/workflows/${id}/recommendations`, { method: 'POST', body: JSON.stringify({ revision, threshold }) }),
  enterWorkflow: (data: { title: string; material: string; content_type: string; source_url: string | null; industry: string; rights_confirmed: boolean }, key: string) => request<Workflow>('/workflow-entry', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken(), 'Idempotency-Key': key }, body: JSON.stringify(data) }),
  attachImage: (workflow: string, artifact: string, unit: string, revision: number, file: File) => request(`/workflows/${workflow}/artifacts/${artifact}/units/${encodeURIComponent(unit)}/image?revision=${revision}`, { method: 'POST', headers: { 'Content-Type': file.type, 'X-CSRF-Token': csrfToken() }, body: file }),
  cancelAgentRun: (id: string) => request(`/agent-runs/${id}/cancel`, { method: 'POST' }),
  auditEvents: () => request<{ id: string; user_id: string; action: string; object_id: string; summary: string; created_at: string }[]>('/audit-events'),
  mcpServers: () => request<MCPServer[]>('/mcp-servers'),
  saveMCP: (data: Omit<MCPServer, 'id' | 'tools' | 'tested_revision' | 'has_token'> & { token?: string; clear_token?: boolean }, id?: string) => request<MCPServer>(`/mcp-servers${id ? `/${id}` : ''}`, { method: id ? 'PUT' : 'POST', body: JSON.stringify(data) }),
  discoverMCP: (id: string) => request<MCPServer>(`/mcp-servers/${id}/discover`, { method: 'POST' }),
  skills: () => request<SkillVersion[]>('/skills'),
  saveSkill: (data: { skill_key: string; base_version: number; manifest: SkillVersion['manifest']; content: string }) => request<SkillVersion>('/skills', { method: 'POST', body: JSON.stringify(data) }),
  publishSkill: (id: string) => request(`/skills/${id}/publish`, { method: 'POST' }),
  previewSkill: (id: string, values: Record<string, string>) => request<{ preview: string }>(`/skills/${id}/preview`, { method: 'POST', body: JSON.stringify(values) }),
  sources: () => request<SourceConfig[]>('/sources'),
  saveSource: (data: SourceInput, id?: string) => request<SourceConfig>(`/sources${id ? `/${id}` : ''}`, { method: id ? 'PUT' : 'POST', body: JSON.stringify(data) }),
  sourceRuns: (id: string) => request<CollectionRun[]>(`/sources/${id}/runs`),
  runSource: (id: string) => request(`/sources/${id}/run`, { method: 'POST' }),
  startAgentRun: (id: string, revision: number, key: string, edit?: { artifact_id: string; unit_id?: string; instruction?: string; operation?: 'review' }) => request<AgentRun>(`/workflows/${id}/agent-runs`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken(), 'Idempotency-Key': key }, body: JSON.stringify({ revision, ...edit }) }),
  agentRuns: (id: string) => request<AgentRun[]>(`/workflows/${id}/agent-runs`),
  runEvents: (id: string) => request<{ id: string; sequence: number; kind: string; summary: string; created_at: string }[]>(`/agent-runs/${id}/events`),
  budget: () => request<{ daily_limit: number; currency: string }>('/budget'),
  saveBudget: (data: { daily_limit: number; currency: string }) => request('/budget', { method: 'PUT', body: JSON.stringify(data) }),
  usage: () => request<{ id: string; day: string; amount: number; status: string }[]>('/budget/usage'),
  testAgentConfig: (agent: string, id: string) => request<{ succeeded: boolean; summary: string }>(`/agent-configs/${agent}/${id}/test`, { method: 'POST' }),
  publishAgentConfig: (agent: string, id: string, expected_active_id: string | null) => request(`/agent-configs/${agent}/${id}/publish`, { method: 'POST', body: JSON.stringify({ expected_active_id }) }),
  workspace: (id: string) => request<Workspace>(`/workflows/${id}/workspace`),
  setMaterial: (id: string, revision: number, material: string) => request(`/workflows/${id}/material`, { method: 'PUT', body: JSON.stringify({ revision, material, rights_confirmed: true }) }),
  chooseProduct: (id: string, revision: number, product_id: string | null) => request(`/workflows/${id}/product`, { method: 'PUT', body: JSON.stringify({ revision, product_id }) }),
  artifacts: (id: string) => request<Artifact[]>(`/workflows/${id}/artifacts`),
  saveDraft: (id: string, revision: number, title: string, units: Artifact['units']) => request<Artifact>(`/workflows/${id}/artifacts`, { method: 'POST', body: JSON.stringify({ revision, title, units }) }),
  finalize: (id: string, revision: number, artifact_id: string) => request(`/workflows/${id}/finalize`, { method: 'POST', body: JSON.stringify({ revision, artifact_id }) }),
  contents: () => request<Artifact[]>('/contents'),
  agentVersions: (agent: string) => request<AgentConfigVersion[]>(`/agent-configs/${agent}`),
  saveAgentConfig: (agent: string, base_version: number, configuration: AgentConfig) => request<AgentConfigVersion>(`/agent-configs/${agent}`, { method: 'POST', body: JSON.stringify({ base_version, configuration }) }),
  validateAgentConfig: (agent: string, configuration: AgentConfig) => request<{ valid: boolean; errors: string[]; preview: string }>(`/agent-configs/${agent}/validate`, { method: 'POST', body: JSON.stringify(configuration) }),
  modelConnections: () => request<ModelConnection[]>('/model-connections'),
  saveModelConnection: (data: ModelConnectionInput, id?: string) => request<ModelConnection>(`/model-connections${id ? `/${id}` : ''}`, { method: id ? 'PUT' : 'POST', body: JSON.stringify(data) }),
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
  products: (q = '', status = '') => request<Product[]>(`/products?q=${encodeURIComponent(q)}${status ? `&product_status=${status}` : ''}`),
  updateProduct: (product: Product, data: { name: string; category: string; description: string; status: string }) => request<Product>(`/products/${product.id}`, { method: 'PUT', body: JSON.stringify({ ...data, expected_name: product.name, expected_category: product.category, expected_description: product.description, expected_status: product.status }) }),
  createProduct: (data: { sku: string; name: string; category: string; description: string; group_id: string }) => request<Product>('/products', { method: 'POST', body: JSON.stringify(data) }),
  assignProductGroup: (productId: string, group_id: string) => request<Product>(`/products/${productId}/group`, { method: 'PATCH', body: JSON.stringify({ group_id }) }),
  hotspots: () => request<Hotspot[]>('/hotspots'),
  createHotspot: (data: { title: string; summary: string; content_type: Hotspot['content_type']; source_url: string | null; industry: string }) => request<Hotspot>('/hotspots', { method: 'POST', body: JSON.stringify(data) }),
  workflows: () => request<Workflow[]>('/workflows'),
  createWorkflow: (hotspot_id: string) => request<Workflow>('/workflows', { method: 'POST', body: JSON.stringify({ hotspot_id }) }),
  events: (id: string) => request<AgentEvent[]>(`/workflows/${id}/events`),
}

export type AgentConfig = {
  primary_model_id: string | null; fallback_model_id: string | null; prompt: string; variables: Record<string, string>;
  temperature: number; max_tokens: number; timeout_seconds: number; retries: number; concurrency: number;
  max_iterations: number; max_tool_calls: number; budget: number;
  skills: { name: string; version: string; content: string; source_version_id?: string | null }[]; allowed_tools: string[];
}
export type AgentConfigVersion = { id: string; agent_type: string; version: number; status: string; configuration: AgentConfig; created_at: string }
export type Workspace = { revision: number; material: string; rights_confirmed: boolean; product_id: string | null; product_snapshot: { name: string; description: string } | null; step: string }
export type Artifact = { id: string; workflow_id: string; version: number; kind: string; title: string; units: { id: string; text: string; image_description: string; shot_size?: string; camera_movement?: string; composition?: string; duration_seconds?: number; image_asset_id?: string | null }[]; status: string; origin: string; content_hash: string; created_at: string; review_status?: string; findings?: { unit_id: string; excerpt: string; reason: string; suggestion: string }[] }
export type AgentRun = { id: string; workflow_id: string; configuration_id: string; workspace_revision: number; status: string; error: string; created_at: string }
export type SourceInput = { name: string; adapter: string; industry: string; keywords: string[]; interval_minutes: number; enabled: boolean; authorization_note: string; revision: number }
export type SourceConfig = SourceInput & { id: string; next_run_at: string }
export type CollectionRun = { id: string; source_revision: number; trigger: string; status: string; summary: string; created_at: string; counts?: { received: number; valid: number; inserted: number; updated: number } }
export type SkillVersion = { id: string; skill_key: string; version: number; status: string; manifest: { name: string; description: string; agents: string[]; industries: string[]; variables: string[] }; content: string; created_at: string }
export type MCPServer = { id: string; revision: number; name: string; endpoint: string; timeout_seconds: number; data_scope: string; enabled: boolean; has_token: boolean; tested_revision: number | null; tools: { name: string; description: string; inputSchema: object }[] }
export type Recommendation = { product_id: string; name: string; score: number; reason: string; evidence: string; semantic_score: number; keyword_score: number; retrieval_score: number }


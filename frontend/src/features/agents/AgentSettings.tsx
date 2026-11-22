import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Tabs, Typography, Modal } from 'antd'
import { api, type AgentConfig, type AgentConfigVersion, type ModelConnection, type SkillVersion } from '../../api'
import ModelConnections from './ModelConnections'
import BudgetSettings from './BudgetSettings'
import SkillLibrary from './SkillLibrary'
import MCPSettings from './MCPSettings'
import RecommendationSettings from './RecommendationSettings'
import { agentPrompts } from './templates'

const agents = ['热点采集', '热点分析', '产品推荐', '文章创作', '美工设计', '视频编剧', '分镜设计', '内容审核']
const keys = ['collector', 'analyst', 'recommender', 'writer', 'designer', 'screenwriter', 'storyboard', 'reviewer']
const tools = ['search_authorized_products', 'get_product_evidence', 'get_hotspot_material', 'read_allowed_asset', 'create_image_candidate', 'check_claims', 'save_draft_candidate']
const defaults: AgentConfig = { primary_model_id: null, fallback_model_id: null, prompt: '', variables: {}, temperature: 0.7, max_tokens: 4096, timeout_seconds: 120, retries: 2, concurrency: 1, max_iterations: 3, max_tool_calls: 10, budget: 0, skills: [], allowed_tools: [] }
type Values = Omit<AgentConfig, 'variables'> & { variable_json: string }

function Editor({ agent }: { agent: string }) {
  const [form] = Form.useForm<Values>()
  const [versions, setVersions] = useState<AgentConfigVersion[]>([])
  const [models, setModels] = useState<ModelConnection[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{ valid: boolean; errors: string[]; preview: string } | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [notice, setNotice] = useState('')
  const [library, setLibrary] = useState<SkillVersion[]>([])
  function fill(config: AgentConfig) { form.setFieldsValue({ ...config, variable_json: JSON.stringify(config.variables, null, 2) }); setResult(null) }
  async function refresh() {
    const [history, connections, skills] = await Promise.all([api.agentVersions(agent), api.modelConnections(), api.skills()])
    setLibrary(skills.filter(s => s.status === 'published' && s.manifest.agents.includes(agent)))
    setVersions(history); setModels(connections); fill(history[0]?.configuration || { ...defaults, prompt: agentPrompts[agent], max_tokens: agent === 'writer' ? 8192 : defaults.max_tokens }); setLoaded(true)
  }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [])
  async function act(save: boolean) {
    setBusy(true); setError(''); setResult(null)
    try {
      const values = await form.validateFields()
      const { variable_json, ...rest } = values
      const variables = JSON.parse(variable_json)
      if (!variables || Array.isArray(variables) || typeof variables !== 'object' || Object.values(variables).some(v => typeof v !== 'string')) throw new Error('变量必须是 JSON 对象，且值均为字符串')
      const config = { ...rest, primary_model_id: rest.primary_model_id || null, fallback_model_id: rest.fallback_model_id || null, variables }
      if (save) { await api.saveAgentConfig(agent, versions[0]?.version || 0, config); await refresh() }
      else setResult(await api.validateAgentConfig(agent, config))
    } catch (e) { setError(e instanceof Error ? e.message : '请检查表单填写') }
    finally { setBusy(false) }
  }
  async function versionAction(id: string, publish: boolean) {
    setBusy(true); setError(''); setNotice('')
    try {
      if (publish) { await api.publishAgentConfig(agent, id, versions.find(v => v.status === 'published')?.id || null); setNotice('版本已发布；工作流执行引擎尚未接入此配置。') }
      else { const result = await api.testAgentConfig(agent, id); setNotice(result.summary) }
      await refresh()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <Space orientation="vertical" style={{ width: '100%' }}>
    <Alert type="info" showIcon title="先保存版本，再执行真实文本模型测试，通过后发布。测试可能计费，需要配置预算及模型价格；工具执行引擎尚未接入。" />
    {notice && <Alert type="success" title={notice} />}
    {error && <Alert type="error" title={error} />}
    <Card title={`独立 Agent 配置 · 最新版本 ${versions[0]?.version || 0}`}>
      <Form form={form} layout="vertical" disabled={busy || !loaded} onValuesChange={() => setResult(null)}>
        <Space wrap>
          <Form.Item name="primary_model_id" label="主模型"><Select allowClear style={{ width: 240 }} options={models.filter(m => m.enabled).map(m => ({ value: m.id, label: `${m.name} / ${m.model_name}` }))} /></Form.Item>
          <Form.Item name="fallback_model_id" label="备用模型"><Select allowClear style={{ width: 240 }} options={models.filter(m => m.enabled).map(m => ({ value: m.id, label: m.name }))} /></Form.Item>
        </Space>
        <Form.Item name="prompt" label="系统提示词（变量写作 {{变量名}}）"><Input.TextArea rows={10} maxLength={50000} /></Form.Item>
        <Button onClick={() => Modal.confirm({ title: '载入内置提示词？', content: '只替换当前编辑区提示词，保存后才创建新版本；原有历史版本不变。', onOk: () => { form.setFieldValue('prompt', agentPrompts[agent]); setResult(null) } })}>载入内置提示词</Button>
        <Form.Item name="variable_json" label="变量预览值（JSON）" rules={[{ required: true }]}><Input.TextArea rows={4} /></Form.Item>
        <Space wrap>{([
          ['temperature', '温度', 0, 2], ['max_tokens', '最大输出 Token', 1, 128000], ['timeout_seconds', '超时（秒）', 1, 600],
          ['retries', '重试次数', 0, 5], ['concurrency', '并发上限', 1, 20], ['max_iterations', '最大循环次数', 1, 20],
          ['max_tool_calls', '最大工具调用数', 0, 100], ['budget', '单次费用上限', 0, 10000],
        ] as const).map(([name, label, min, max]) => <Form.Item key={name} name={name} label={label} rules={[{ required: true }]}><InputNumber min={min} max={max} step={name === 'temperature' || name === 'budget' ? 0.1 : 1} /></Form.Item>)}</Space>
        <Form.Item name="allowed_tools" label="内部工具白名单（执行时仍需鉴权）"><Select mode="multiple" options={tools.map(value => ({ value, label: value }))} /></Form.Item>
        <Typography.Title level={5}>Skill 版本快照</Typography.Title>
        <Select style={{ width: '100%' }} value={undefined} placeholder="绑定已发布的 Skill 版本" options={library.map(s => ({ value: s.id, label: `${s.manifest.name} · v${s.version}` }))} onChange={id => { const s = library.find(row => row.id === id); if (s) form.setFieldValue('skills', [...(form.getFieldValue('skills') || []), { name: s.manifest.name, version: String(s.version), content: s.content, source_version_id: s.id }]) }} />
        <Form.List name="skills">{(fields, { add, remove }) => <>{fields.map(field => <Card key={field.key} size="small" extra={<Button danger onClick={() => remove(field.name)}>移除</Button>}>
          <Form.Item name={[field.name, 'source_version_id']} hidden><Input /></Form.Item>
          <Form.Item name={[field.name, 'name']} label="Skill 名称" rules={[{ required: true }]}><Input maxLength={100} /></Form.Item>
          <Form.Item name={[field.name, 'version']} label="版本标识" rules={[{ required: true }]}><Input maxLength={40} /></Form.Item>
          <Form.Item name={[field.name, 'content']} label="SKILL.md 正文" rules={[{ required: true }]}><Input.TextArea rows={5} maxLength={30000} /></Form.Item>
        </Card>)}<Button onClick={() => add({ name: '', version: '1', content: '' })}>添加 Skill</Button></>}</Form.List>
        <Space style={{ marginTop: 16 }}><Button type="primary" loading={busy} onClick={() => act(true)}>保存新版本</Button><Button loading={busy} onClick={() => act(false)}>校验配置与预览变量</Button></Space>
      </Form>
    </Card>
    {result && <Card title={result.valid ? '静态配置校验通过' : '配置需要完善'}>{result.errors.map(e => <Alert key={e} type="error" title={e} />)}<Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{result.preview}</Typography.Paragraph></Card>}
    <Card title="历史版本"><Select placeholder="载入历史版本编辑（另存为新版本）" style={{ width: '100%' }} value={undefined} onChange={id => { const row = versions.find(v => v.id === id); if (row) fill(row.configuration) }} options={versions.map(v => ({ value: v.id, label: `v${v.version} · ${new Date(v.created_at).toLocaleString()} · ${v.status === 'published' ? '已发布' : v.status === 'retired' ? '已替换' : '草稿'}` }))} />
      {versions.map(v => <Space key={v.id} wrap style={{ display: 'flex', marginTop: 8 }}><Typography.Text>v{v.version} · {v.status === 'published' ? '生效版本' : '未生效'}</Typography.Text>
        <Button disabled={busy} onClick={() => Modal.confirm({ title: `真实测试 v${v.version}？`, content: '会向所选主备模型发送提示词、Skill 与预览变量，可能产生费用。', onOk: () => versionAction(v.id, false) })}>真实文本测试</Button>
        <Button disabled={busy || v.status === 'published'} onClick={() => Modal.confirm({ title: `发布 v${v.version}？`, content: '主备连接须已通过真实测试。选择历史版本发布即回滚到该版本。', onOk: () => versionAction(v.id, true) })}>{v.status === 'retired' ? '回滚到此版本' : '发布此版本'}</Button>
      </Space>)}
    </Card>
  </Space>
}

export default function AgentSettings() {
  return <Tabs destroyOnHidden items={[
    { key: 'agents', label: 'Agent 管理', children: <Tabs tabPosition="left" destroyOnHidden items={keys.map((key, i) => ({ key, label: agents[i], children: <Editor agent={key} /> }))} /> },
    { key: 'models', label: '模型连接', children: <ModelConnections /> },
    { key: 'skills', label: 'Skill 版本库', children: <SkillLibrary /> },
    { key: 'retrieval', label: '推荐检索', children: <RecommendationSettings /> },
    { key: 'budget', label: '预算与用量', children: <BudgetSettings /> },
    { key: 'mcp', label: 'MCP 与工具', children: <MCPSettings /> },
  ]} />
}

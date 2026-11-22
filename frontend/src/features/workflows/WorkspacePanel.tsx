import { useEffect, useState } from 'react'
import { Alert, Button, Card, Checkbox, Empty, Input, InputNumber, Modal, Select, Space, Typography, Timeline, Upload, Image } from 'antd'
import { api, type Workspace, type Artifact, type Product, type AgentRun, type Recommendation } from '../../api'

export default function WorkspacePanel({ workflowId, onChange }: { workflowId: string; onChange: () => void }) {
  const [state, setState] = useState<Workspace | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [material, setMaterial] = useState('')
  const [rights, setRights] = useState(false)
  const [productId, setProductId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [units, setUnits] = useState<Artifact['units']>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [runEvents, setRunEvents] = useState<{ id: string; sequence: number; kind: string; summary: string; created_at: string }[]>([])
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null)
  const [editUnitId, setEditUnitId] = useState<string | null>(null)
  const [instruction, setInstruction] = useState('')
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [recommendationNotice, setRecommendationNotice] = useState('')
  const [showSearch, setShowSearch] = useState(false)
  async function refresh() {
    const s = await api.workspace(workflowId)
    const [a, p] = await Promise.all([api.artifacts(workflowId), api.products('', 'active')])
    setState(s); setArtifacts(a); setProducts(p); setMaterial(s.material); setRights(s.rights_confirmed); setProductId(s.product_id)
    const latest = a.find(v => v.status !== 'stale' && (s.step !== 'storyboarding' || v.kind === 'storyboard'))
    setSelectedArtifact(latest?.id || null)
    setTitle(latest?.title || ''); setUnits(latest?.units || [{ id: crypto.randomUUID(), text: '', image_description: '' }]); setDirty(false)
  }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [workflowId])
  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const rows = await api.agentRuns(workflowId)
        const events = rows[0] ? await api.runEvents(rows[0].id) : []
        if (active) { setRuns(rows); setRunEvents(events) }
      } catch (e) { if (active) setError((e as Error).message) }
    }
    void poll(); const timer = window.setInterval(poll, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [workflowId])
  const latestRunId = runs[0]?.id
  useEffect(() => {
    if (!latestRunId) return
    const source = new EventSource(`/api/v1/agent-runs/${latestRunId}/events/stream`)
    source.onmessage = event => {
      const item = JSON.parse(event.data)
      setRunEvents(current => [...current.filter(e => e.id !== item.id), item].sort((a, b) => a.sequence - b.sequence))
    }
    source.addEventListener('finished', () => source.close())
    source.addEventListener('access_revoked', () => { source.close(); setRunEvents([]); setError('会话或产品授权已变化，请刷新页面') })
    return () => source.close()
  }, [latestRunId])
  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await action(); await refresh(); onChange() }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  if (!state) return error ? <Alert type="error" title={error} /> : <Empty description="正在读取工作流资料" />
  const latest = artifacts.find(a => a.id === selectedArtifact)
  const pending = runs.some(r => r.status === 'queued' || r.status === 'running')
  return <Space orientation="vertical" style={{ width: '100%', marginBottom: 24 }}>
    {error && <Alert type="error" title={error} />}
    <Card title="参考素材确认">
      <Typography.Paragraph>粘贴有权使用的文章正文或视频文字稿。仅有链接或摘要不能代表系统已取得原始素材。</Typography.Paragraph>
      <Input.TextArea rows={6} value={material} disabled={busy || state.step === 'completed'} maxLength={100000} onChange={e => setMaterial(e.target.value)} />
      <Checkbox checked={rights} disabled={busy || state.step === 'completed'} onChange={e => setRights(e.target.checked)}>我确认有权使用所提交的素材</Checkbox>
      <Button disabled={busy || !rights || material.trim().length < 20 || state.step === 'completed'} onClick={() => Modal.confirm({ title: '确认参考素材？', content: '重新确认会使已有产品选择和草稿失效。', onOk: () => perform(() => api.setMaterial(workflowId, state.revision, material)) })}>确认素材</Button>
    </Card>
    {state.step === 'product_selection' && <Card title="选择推荐产品或无产品继续">
      <Space wrap>{[65, 60].map(threshold => <Button key={threshold} disabled={busy} onClick={() => Modal.confirm({ title: `获取适配分 ≥ ${threshold} 的推荐？`, content: '将参考素材发送给已配置的嵌入与推荐模型，按预算计费。仅授权产品参与召回。', onOk: async () => { setBusy(true); setError(''); try { const result = await api.recommendations(workflowId, state.revision, threshold); setRecommendations(result.items); setRecommendationNotice(result.notice) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } } })}>{threshold === 65 ? '推荐产品（≥65分）' : '降低到60分再推荐'}</Button>)}<Button onClick={() => setShowSearch(true)}>搜索全部授权产品</Button><Button onClick={() => setProductId(null)}>无产品继续</Button></Space>
      {recommendationNotice && <Alert type="info" title={recommendationNotice} />}
      {recommendations.map(item => <Card key={item.product_id} size="small" title={`${item.name} · ${item.score} 分`} extra={<Button onClick={() => setProductId(item.product_id)}>选择此产品</Button>}><Typography.Paragraph>{item.reason}</Typography.Paragraph><Typography.Paragraph>产品依据：{item.evidence}</Typography.Paragraph><Typography.Text type="secondary">向量 {item.semantic_score} / 关键词 {item.keyword_score} / 召回 {item.retrieval_score}</Typography.Text></Card>)}
      {showSearch && <Select showSearch optionFilterProp="label" allowClear style={{ width: '100%' }} value={productId} placeholder="搜索启用的授权产品" onChange={v => setProductId(v || null)} options={products.map(p => ({ value: p.id, label: `${p.name} · ${p.sku}` }))} />}
      <Typography.Paragraph>当前选择：{products.find(p => p.id === productId)?.name || '无产品'}</Typography.Paragraph>
      <Button type="primary" disabled={busy} onClick={() => perform(() => api.chooseProduct(workflowId, state.revision, productId))}>确认产品选择</Button>
    </Card>}
    {state.product_snapshot && <Card title={`已选产品 · ${state.product_snapshot.name}`}><Typography.Paragraph>{state.product_snapshot.description}</Typography.Paragraph></Card>}
    {state.step === 'storyboarding' && artifacts.find(a => a.kind === 'script' && a.status === 'approved') && <Card title="已确认剧本（分镜输入）">{artifacts.find(a => a.kind === 'script' && a.status === 'approved')?.units.map(u => <Typography.Paragraph key={u.id}>{u.text}</Typography.Paragraph>)}</Card>}
    {(state.step === 'drafting' || state.step === 'storyboarding' || state.step === 'completed') && <Card title={state.step === 'storyboarding' ? '分镜设计与确认' : '内容版本与人工编辑'}>
      <Alert type="info" title="可生成候选、逐段编辑、填入人工配图并按需审核。正文保存为新版本后，旧配图与审核结论需重新确认。自动美工生图尚未接入。" />
      {state.step !== 'completed' && <Space wrap><Button loading={busy || pending} disabled={dirty || pending} onClick={() => Modal.confirm({ title: '生成候选内容？', content: '使用对应已发布的创作 Agent，按预算调用模型。未保存的修改请先保存。', onOk: () => perform(() => api.startAgentRun(workflowId, state.revision, crypto.randomUUID())) })}>{state.step === 'storyboarding' ? '运行分镜 Agent' : '运行创作 Agent'}</Button><Button disabled={busy} onClick={() => perform(async () => {})}>刷新候选</Button></Space>}
      <Select style={{ width: '100%' }} value={selectedArtifact} placeholder="选择候选或历史版本" onChange={id => { const row = artifacts.find(a => a.id === id); if (row) { setSelectedArtifact(id); setTitle(row.title); setUnits(row.units); setDirty(false) } }} options={artifacts.filter(a => a.status !== 'stale').map(a => ({ value: a.id, label: `v${a.version} · ${a.title} · ${a.origin === 'agent' ? 'Agent' : '人工'}` }))} />
      <Input value={title} maxLength={300} placeholder="稿件标题" disabled={busy || state.step === 'completed'} onChange={e => { setTitle(e.target.value); setDirty(true) }} />
      {units.map((unit, i) => <Card key={unit.id} size="small" title={`段落 / 场景 ${i + 1}`} extra={state.step !== 'completed' && <Space><Button disabled={busy || pending || dirty || !latest} onClick={() => { setEditUnitId(unit.id); setInstruction('') }}>Agent 局部修改</Button><Button danger disabled={busy || units.length === 1} onClick={() => { setUnits(units.filter(u => u.id !== unit.id)); setDirty(true) }}>移除</Button></Space>}>
        <Input.TextArea rows={4} value={unit.text} disabled={busy || state.step === 'completed'} onChange={e => { setUnits(units.map(u => u.id === unit.id ? { ...u, text: e.target.value } : u)); setDirty(true) }} />
        <Input value={unit.image_description} placeholder="图片占位或画面描述" disabled={busy || state.step === 'completed'} onChange={e => { setUnits(units.map(u => u.id === unit.id ? { ...u, image_description: e.target.value } : u)); setDirty(true) }} />
        {latest?.kind === 'script' && <InputNumber value={unit.duration_seconds} min={0.1} max={60} addonAfter="场景秒数" disabled={busy || state.step === 'completed'} onChange={value => { setUnits(units.map(u => u.id === unit.id ? { ...u, duration_seconds: value || 0 } : u)); setDirty(true) }} />}
        {unit.image_asset_id && <Image width={240} src={`/api/v1/workflows/${workflowId}/assets/${unit.image_asset_id}`} alt={unit.image_description || '稿件配图'} />}
        {state.step !== 'completed' && !!unit.image_description && latest && <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} disabled={busy || dirty || pending} beforeUpload={file => { void perform(() => api.attachImage(workflowId, latest.id, unit.id, state.revision, file)); return false }}><Button disabled={busy || dirty || pending}>上传此处配图（最多10MB）</Button></Upload>}
        {(state.step === 'storyboarding' || latest?.kind === 'storyboard') && <Space wrap>
          {(['shot_size', 'camera_movement', 'composition'] as const).map((key, index) => <Input key={key} value={unit[key]} placeholder={['景别', '运镜', '构图'][index]} disabled={busy || state.step === 'completed'} onChange={e => { setUnits(units.map(u => u.id === unit.id ? { ...u, [key]: e.target.value } : u)); setDirty(true) }} />)}
          <InputNumber value={unit.duration_seconds} min={0.1} max={60} addonAfter="秒" disabled={busy || state.step === 'completed'} onChange={value => { setUnits(units.map(u => u.id === unit.id ? { ...u, duration_seconds: value || 0 } : u)); setDirty(true) }} />
        </Space>}
      </Card>)}
      {state.step !== 'completed' && <Space wrap>
        <Button disabled={busy} onClick={() => { setUnits([...units, { id: crypto.randomUUID(), text: '', image_description: '' }]); setDirty(true) }}>添加段落 / 场景</Button>
        <Button type="primary" disabled={busy || !title.trim() || units.some(u => !u.text.trim())} onClick={() => perform(() => api.saveDraft(workflowId, state.revision, title, units))}>保存新版本</Button>
        <Button disabled={busy || pending || dirty || !latest} onClick={() => Modal.confirm({ title: '触发可选 AI 审核？', content: '使用已发布的内容审核 Agent 检查当前版本，可能产生费用。审核后修改内容须重新审核。', onOk: () => latest && perform(() => api.startAgentRun(workflowId, state.revision, crypto.randomUUID(), { artifact_id: latest.id, operation: 'review' })) })}>AI 审核（可选）</Button>
        <Button disabled={busy || dirty || !latest} onClick={() => Modal.confirm({ title: latest?.kind === 'script' ? '确认剧本并进入分镜？' : '确认保存成果？', content: '确认当前版本，保留其实际审核状态；剧本确认后进入分镜设计。', onOk: () => latest && perform(() => api.finalize(workflowId, state.revision, latest.id)) })}>{latest?.kind === 'script' ? '确认剧本，进入分镜' : '确认成果'}</Button>
      </Space>}
      <Typography.Paragraph>历史版本：{artifacts.map(v => `v${v.version}${v.status === 'stale' ? '（已失效）' : ''}`).join('、') || '暂无'}</Typography.Paragraph>
      {latest && <Alert type={latest.review_status === 'AI审核通过' ? 'success' : 'info'} title={`当前版本：${latest.review_status || '未审核'}`} />}
      {latest?.findings?.map((finding, i) => <Card key={i} size="small" title={`段落 ${finding.unit_id}`}><Typography.Paragraph>原文：{finding.excerpt}</Typography.Paragraph><Typography.Paragraph>{finding.reason}</Typography.Paragraph><Typography.Paragraph>建议：{finding.suggestion}</Typography.Paragraph></Card>)}
      {state.step === 'completed' && latest && <Button href={`/api/v1/contents/${latest.id}/download`}>下载成果（Markdown / 图片包）</Button>}
    </Card>}
    {runs.length > 0 && <Card title="Agent 执行过程"><Typography.Paragraph>最新任务：{({ queued: '排队中', running: '执行中', completed: '等待人工确认', failed: '失败', uncertain: '中断待核对', cancelled: '已取消' }[runs[0].status] || runs[0].status)}</Typography.Paragraph>{pending && <Button danger disabled={busy} onClick={() => Modal.confirm({ title: '取消当前任务？', content: '已发出的模型请求可能仍计费，结果不会提交。', onOk: () => perform(() => api.cancelAgentRun(runs[0].id)) })}>取消任务</Button>}{runs[0].error && <Alert type="error" title={runs[0].error} />}<Timeline items={runEvents.map(e => ({ content: <><Typography.Text>{e.summary}</Typography.Text><br /><Typography.Text type="secondary">{new Date(e.created_at).toLocaleString()}</Typography.Text></> }))} /></Card>}
    <Modal title="描述本段需要如何修改" open={!!editUnitId} confirmLoading={busy} onCancel={() => setEditUnitId(null)} okButtonProps={{ disabled: !instruction.trim() || pending }} onOk={() => { if (latest && editUnitId) void perform(async () => { await api.startAgentRun(workflowId, state.revision, crypto.randomUUID(), { artifact_id: latest.id, unit_id: editUnitId, instruction }); setEditUnitId(null) }) }}>
      <Typography.Paragraph>只允许修改所选段落。标题及其他段落由系统逐字校验，超出范围的结果不会成为可用候选。</Typography.Paragraph>
      <Input.TextArea rows={4} maxLength={2000} value={instruction} onChange={e => setInstruction(e.target.value)} />
    </Modal>
  </Space>
}

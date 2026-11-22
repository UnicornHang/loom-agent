import { Button, Input, Select, Form, Menu, Table, Card, Steps, Timeline, Alert, Layout, Modal as AntModal, Empty as AntEmpty } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type AgentEvent, type Hotspot, type Product, type ProductGroup, type User, type Workflow } from './api'
import AdminPanel from './features/admin/AdminPanel'
import ProductImages from './features/products/ProductImages'
import ProductEditor from './features/products/ProductEditor'
import LoginScreen from './features/auth/LoginScreen'
import AgentSettings from './features/agents/AgentSettings'
import WorkspacePanel from './features/workflows/WorkspacePanel'
import WorkflowEntry from './features/workflows/WorkflowEntry'
import ContentLibrary from './features/contents/ContentLibrary'
import SourceSettings from './features/sources/SourceSettings'
import AuditLog from './features/admin/AuditLog'

type Page = 'entry' | 'sources' | 'contents' | 'overview' | 'hotspots' | 'workflows' | 'products' | 'agents' | 'logs' | 'settings'
const menu: { key: Page; label: string; mark: string }[] = [
  { key: 'overview', label: '总览', mark: '◫' },
  { key: 'hotspots', label: '热点信息大厅', mark: '⌁' },
  { key: 'entry', label: '工作流入口', mark: '↗' },
  { key: 'workflows', label: '工作流', mark: '◇' },
  { key: 'products', label: '产品库', mark: '▣' },
  { key: 'sources', label: '采集来源', mark: '◉' },
  { key: 'contents', label: '内容创作', mark: '▤' },
  { key: 'agents', label: 'Agent 配置', mark: '✳' },
  { key: 'logs', label: '运行日志', mark: '≡' },
  { key: 'settings', label: '成员与授权', mark: '⚙' },
]
const stages = ['发现内容', '分析热点', '选择产品', '生成内容', '设计素材', '确认保存']

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function badge(type: Hotspot['content_type']) {
  return type === 'video' ? '视频' : type === 'article' ? '图文' : '纯文字'
}

export default function App() {
  const [page, setPage] = useState<Page>('overview')
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [imageProduct, setImageProduct] = useState<Product | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [products, setProducts] = useState<Product[]>([])
  const [groups, setGroups] = useState<ProductGroup[]>([])
  const [hotspots, setHotspots] = useState<Hotspot[]>([])
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [showProductForm, setShowProductForm] = useState(false)
  const [showHotspotForm, setShowHotspotForm] = useState(false)
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [passwordDraft, setPasswordDraft] = useState({ current_password: '', new_password: '' })
  const [productDraft, setProductDraft] = useState({ sku: '', name: '', category: '', description: '', group_id: '' })
  const [hotspotDraft, setHotspotDraft] = useState({ title: '', summary: '', content_type: 'article' as Hotspot['content_type'], source_url: '', industry: '3C' })

  async function refresh() {
    try {
      const [health, p, h, w, g] = await Promise.all([api.health(), api.products(), api.hotspots(), api.workflows(), api.groups()])
      setConnected(health.status === 'ok')
      setProducts(p); setHotspots(h); setWorkflows(w); setGroups(g); setError('')
      setProductDraft(current => ({ ...current, group_id: current.group_id || g[0]?.id || '' }))
    } catch (e) { setConnected(false); if (e instanceof ApiError && e.status === 401) setUser(null); else setError((e as Error).message) }
  }

  useEffect(() => {
    void api.me().then(me => { setUser(me); void refresh() }).catch(() => setUser(null)).finally(() => setAuthLoading(false))
  }, [])
  useEffect(() => {
    const expireSession = () => {
      setUser(null)
      setProducts([]); setHotspots([]); setWorkflows([]); setGroups([])
      setEvents([]); setSelectedWorkflow(null); setPage('overview')
      setShowProductForm(false); setShowHotspotForm(false); setShowPasswordForm(false)
    }
    window.addEventListener('loom:unauthorized', expireSession)
    return () => window.removeEventListener('loom:unauthorized', expireSession)
  }, [])
  useEffect(() => {
    if (authLoading) return
    const redirect = () => {
      if (!user && window.location.pathname !== '/login') {
        window.history.replaceState(null, '', '/login')
      } else if (user && window.location.pathname === '/login') {
        window.history.replaceState(null, '', '/')
      }
    }
    redirect()
    window.addEventListener('popstate', redirect)
    return () => window.removeEventListener('popstate', redirect)
  }, [authLoading, user])
  useEffect(() => {
    if (!selectedWorkflow) return
    void api.events(selectedWorkflow).then(setEvents).catch(e => setError((e as Error).message))
  }, [selectedWorkflow])

  const selected = useMemo(() => workflows.find(w => w.id === selectedWorkflow), [workflows, selectedWorkflow])
  const selectedHotspot = hotspots.find(h => h.id === selected?.hotspot_id)

  async function submitProduct(event: React.FormEvent) {
    event.preventDefault(); setBusy(true)
    try { await api.createProduct(productDraft); setProductDraft({ sku: '', name: '', category: '', description: '', group_id: groups[0]?.id || '' }); setShowProductForm(false); await refresh() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function assignProductGroup(productId: string, groupId: string) {
    try { await api.assignProductGroup(productId, groupId); await refresh() }
    catch (e) { setError((e as Error).message) }
  }
  async function submitHotspot(event: React.FormEvent) {
    event.preventDefault(); setBusy(true)
    try { await api.createHotspot({ ...hotspotDraft, source_url: hotspotDraft.source_url || null }); setHotspotDraft({ title: '', summary: '', content_type: 'article', source_url: '', industry: '3C' }); setShowHotspotForm(false); await refresh() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function startWorkflow(hotspotId: string) {
    setBusy(true)
    try { const workflow = await api.createWorkflow(hotspotId); await refresh(); setSelectedWorkflow(workflow.id); setPage('workflows') }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function login(username: string, password: string) {
    const loggedIn = await api.login(username, password)
    setUser(loggedIn)
    await refresh()
  }

  async function logout() {
    try { await api.logout() } finally { setUser(null); setProducts([]); setHotspots([]); setWorkflows([]); setGroups([]); setPage('overview') }
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault(); setBusy(true)
    try { await api.changePassword(passwordDraft.current_password, passwordDraft.new_password); setShowPasswordForm(false); setPasswordDraft({ current_password: '', new_password: '' }); setUser(null) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  const visibleMenu = menu.filter(item => item.key !== 'settings' || user?.role === 'admin')
  if (authLoading) return <div className="auth-loading">正在检查登录状态…</div>
  if (!user) return <LoginScreen onLogin={login}/>

  return <div className="shell">
    <Layout.Sider width={248} className="sidebar">
      <div className="brand"><div className="brand-mark"><span></span><span></span><span></span></div><div><strong>loom</strong><small>CONTENT STUDIO</small></div></div>
      <div className="workspace-label">工作空间 <span>01</span></div>
      <Menu theme="dark" mode="inline" selectedKeys={[page]} items={visibleMenu.map(item => ({ key: item.key, label: item.label }))} onClick={({ key }) => setPage(key as Page)}/>
      <div className="sidebar-bottom"><div className="sidebar-rule"/><p>当前阶段</p><strong>创作与版本管理</strong><small>模型连接由管理员配置</small></div>
    </Layout.Sider>
    <main className="main">
      <header className="topbar"><div className="crumb">内容工作台 <span>/</span> {menu.find(x => x.key === page)?.label}</div><div className="top-actions"><span className={`connection ${connected ? 'online' : ''}`}><i/>{connected ? 'API 已连接' : 'API 未连接'}</span><span className="signed-user">{user.username}</span><Button className="text-link" onClick={() => setShowPasswordForm(true)}>修改密码</Button><Button className="ghost logout" onClick={() => void logout()}>退出</Button></div></header>
      {error && <div className="error-banner"><span>{error}</span><Button onClick={() => { setError(''); void refresh() }}>重试</Button></div>}
      <div className="content">
        {page === 'overview' && <><div className="eyebrow">LOOM / OVERVIEW</div><div className="heading-row"><div><h1>让好内容<br/><em>开始流动。</em></h1><p className="lead">从种草灵感到可发布的内容，保持每一步都可看、可改、可追溯。</p></div><div className="edition">BUILD 001<span>工作台预览</span></div></div><div className="quick-grid"><Button className="quick-card dark" onClick={() => { setPage('hotspots'); setShowHotspotForm(true) }}><div className="quick-top"><span>01 / 从内容开始</span><b>↗</b></div><h2>添加一条灵感</h2><p>粘贴你找到的文章或视频，开始创建工作流。</p><div className="quick-foot">手动导入 · 立即可用</div></Button><Button className="quick-card" onClick={() => setPage('products')}><div className="quick-top"><span>02 / 准备产品</span><b>↗</b></div><h2>建立产品资料</h2><p>产品信息会成为后续推荐与创作的事实依据。</p><div className="quick-foot">已录入 {products.length} 个产品</div></Button></div><div className="section-title"><h3>流程概览</h3><span>从发现到定稿</span></div><Steps current={-1} items={stages.map(title => ({ title }))}/><div className="section-title lower"><h3>最近工作流</h3><Button className="text-link" onClick={() => setPage('workflows')}>查看全部 →</Button></div><WorkflowList workflows={workflows.slice(0, 3)} hotspots={hotspots} onOpen={id => { setSelectedWorkflow(id); setPage('workflows') }}/></>}
        {page === 'hotspots' && <><PageHeading eyebrow="DISCOVERY / 01" title="热点信息大厅" intro="收集高表现种草作品。当前来源为手动导入，自动采集接入后会在这里显示。" action={<Button className="primary" onClick={() => setShowHotspotForm(true)}>＋ 添加内容</Button>}/><div className="notice"><span>◉</span><div><strong>采集来源尚未接入</strong><p>列表中的内容由团队手动提交，不会显示为自动抓取的热点。</p></div></div><div className="list-header"><span>内容列表</span><small>{hotspots.length} 条内容</small></div>{hotspots.length ? <div className="hotspot-grid">{hotspots.map(h => <Card className="hotspot-card" key={h.id}><div className="card-meta"><span className="pill">{badge(h.content_type)}</span><span>手动导入</span></div><h3>{h.title}</h3><p>{h.summary || '暂无摘要。进入工作流前请补充有权使用的原始素材。'}</p><div className="card-bottom"><small>{formatDate(h.created_at)}</small><Button onClick={() => void startWorkflow(h.id)} disabled={busy}>开始创作 ↗</Button></div></Card>)}</div> : <Empty title="还没有热点内容" body="添加你找到的种草图文或视频，作为第一条创作素材。"/>}</>}
        {page === 'entry' && <><PageHeading eyebrow="CREATE / 02" title="工作流入口" intro="提交你自己的参考素材，从这里开始创作。" />{['admin', 'creator'].includes(user.role) ? <WorkflowEntry onCreated={id => { void refresh().then(() => { setSelectedWorkflow(id); setPage('workflows') }) }} /> : <Alert type="info" title="当前账号没有创建工作流权限" />}</>}
        {page === 'workflows' && <><PageHeading eyebrow="WORKFLOWS / 02" title="工作流" intro="每一次创作都保留节点、版本和执行记录。"/>{selected ? <div className="workflow-detail"><Button className="back" onClick={() => setSelectedWorkflow(null)}>← 返回列表</Button><div className="detail-head"><div><span className="pill">{selected.current_step === 'completed' ? '成果已保存' : selected.current_step === 'drafting' ? '创作与确认' : '等待资料确认'}</span><h2>{selectedHotspot?.title || '未命名工作流'}</h2><p>工作流 ID · {selected.id.slice(0, 12)}</p></div></div><WorkspacePanel key={selected.id} workflowId={selected.id} onChange={() => { void refresh(); void api.events(selected.id).then(setEvents) }} /><Card title="工作流操作记录"><Timeline items={events.map(e => ({ content: <><strong>{e.title}</strong><p>{e.summary}</p><small>{formatDate(e.created_at)}</small></> }))} /></Card></div> : <WorkflowList workflows={workflows} hotspots={hotspots} onOpen={setSelectedWorkflow}/>}</>}
        {page === 'products' && <><PageHeading eyebrow="CATALOG / 03" title="产品库" intro="这里只显示你有权查看的产品。产品资料是后续推荐与创作的事实依据。" action={['admin', 'product_manager'].includes(user.role) ? <Button className="primary" onClick={() => setShowProductForm(true)}>＋ 新建产品</Button> : undefined}/><div className="list-header"><span>可见产品</span><small>{products.length} 个 SKU</small></div><Table<Product> rowKey="id" dataSource={products} pagination={{ pageSize: 10, hideOnSinglePage: true }} columns={[{ title: '产品', dataIndex: 'name' }, { title: 'SKU', dataIndex: 'sku' }, { title: '品类', dataIndex: 'category' }, { title: '分组', render: (_, p) => user.role === 'admin' ? <Select style={{ minWidth: 140 }} value={p.group_id || undefined} placeholder="未分组" options={groups.map(g => ({ value: g.id, label: g.name }))} onChange={value => void assignProductGroup(p.id, value)}/> : groups.find(g => g.id === p.group_id)?.name || '未分组' }, { title: '状态', dataIndex: 'status' }, { title: '维护', render: (_, p) => ['admin', 'product_manager'].includes(user.role) ? <Button type="link" onClick={() => setEditingProduct(p)}>编辑资料</Button> : '只读' }, { title: '素材', render: (_, p) => <Button type="link" onClick={() => setImageProduct(p)}>产品图片</Button> }]}/></>}
        {page === 'sources' && <><PageHeading eyebrow="SOURCES / 06" title="采集来源" intro="管理行业订阅、调度与执行记录。" />{user.role === 'admin' ? <SourceSettings /> : <Alert type="info" title="采集来源由管理员维护" />}</>}
        {page === 'contents' && <><PageHeading eyebrow="CONTENTS / 05" title="内容创作" intro="已确认保存的内容与版本记录。" /><ContentLibrary /></>}
        {page === 'agents' && <><PageHeading eyebrow="AGENTS / 04" title="Agent 配置" intro="管理模型、提示词、Skill 和执行权限。"/>{user.role === 'admin' ? <AgentSettings /> : <Alert type="info" title="Agent 全局配置由管理员维护" />}</>}
        {page === 'logs' && <><PageHeading eyebrow="ACTIVITY / 05" title="运行日志" intro="查看工作流创建与 Agent 执行过程。"/>{user.role === 'admin' && <AuditLog />}<div className="list-header"><span>事件</span><small>按工作流查看</small></div><WorkflowList workflows={workflows} hotspots={hotspots} onOpen={id => { setSelectedWorkflow(id); setPage('workflows') }}/></>}
        {page === 'settings' && user.role === 'admin' && <><PageHeading eyebrow="ACCESS / 06" title="成员与授权" intro="创建成员、建立产品分组，并决定各成员可见的产品范围。"/><AdminPanel currentUserId={user.id} onGroupsChanged={() => { void refresh() }}/></>}
      </div>
    </main>
    {editingProduct && <ProductEditor product={editingProduct} onClose={() => setEditingProduct(null)} onSaved={() => void refresh()} />}
    {imageProduct && <Modal title={`${imageProduct.name} · 产品图片`} onClose={() => setImageProduct(null)}><ProductImages productId={imageProduct.id} writable={["admin", "product_manager"].includes(user.role)}/></Modal>}
    {showProductForm && <Modal title="新建产品" onClose={() => setShowProductForm(false)}><Form onSubmitCapture={submitProduct} className="form"><label>产品分组<Select  value={productDraft.group_id} onChange={e => setProductDraft({ ...productDraft, group_id: e })}><Select.Option value="">选择分组</Select.Option>{groups.map(group => <Select.Option key={group.id} value={group.id}>{group.name}</Select.Option>)}</Select></label>{!groups.length && <p className="form-help">请先由管理员在“成员与授权”中创建产品分组。</p>}<label>产品名称<Input required value={productDraft.name} onChange={e => setProductDraft({ ...productDraft, name: e.target.value })} placeholder="例如：开放式蓝牙耳机"/></label><label>SKU<Input required value={productDraft.sku} onChange={e => setProductDraft({ ...productDraft, sku: e.target.value })} placeholder="例如：EAR-001"/></label><label>品类<Input required value={productDraft.category} onChange={e => setProductDraft({ ...productDraft, category: e.target.value })} placeholder="例如：耳机"/></label><label>产品描述<Input.TextArea value={productDraft.description} onChange={e => setProductDraft({ ...productDraft, description: e.target.value })} placeholder="填写已核实的产品资料"/></label><div className="form-actions"><Button htmlType="button" className="ghost" onClick={() => setShowProductForm(false)}>取消</Button><Button htmlType="submit" className="primary" disabled={busy || !productDraft.group_id}>保存产品</Button></div></Form></Modal>}
    {showHotspotForm && <Modal title="添加内容灵感" onClose={() => setShowHotspotForm(false)}><Form onSubmitCapture={submitHotspot} className="form"><label>标题<Input required value={hotspotDraft.title} onChange={e => setHotspotDraft({ ...hotspotDraft, title: e.target.value })} placeholder="这条内容讲了什么？"/></label><label>内容类型<Select value={hotspotDraft.content_type} onChange={e => setHotspotDraft({ ...hotspotDraft, content_type: e as Hotspot['content_type'] })}><Select.Option value="article">图文</Select.Option><Select.Option value="video">视频</Select.Option><Select.Option value="text">纯文字</Select.Option></Select></label><label>原文链接<Input value={hotspotDraft.source_url} onChange={e => setHotspotDraft({ ...hotspotDraft, source_url: e.target.value })} placeholder="https://..."/></label><label>摘要<Input.TextArea value={hotspotDraft.summary} onChange={e => setHotspotDraft({ ...hotspotDraft, summary: e.target.value })} placeholder="写下值得借鉴的角度；生成前仍需提供可用素材"/></label><div className="form-actions"><Button htmlType="button" className="ghost" onClick={() => setShowHotspotForm(false)}>取消</Button><Button htmlType="submit" className="primary" disabled={busy}>添加内容</Button></div></Form></Modal>}
    {showPasswordForm && <Modal title="修改密码" onClose={() => setShowPasswordForm(false)}><Form onSubmitCapture={changePassword} className="form"><label>当前密码<Input type="password" autoComplete="current-password" required value={passwordDraft.current_password} onChange={e => setPasswordDraft({ ...passwordDraft, current_password: e.target.value })}/></label><label>新密码<Input type="password" autoComplete="new-password" required minLength={12} value={passwordDraft.new_password} onChange={e => setPasswordDraft({ ...passwordDraft, new_password: e.target.value })} placeholder="至少 12 位"/></label><div className="form-actions"><Button htmlType="button" className="ghost" onClick={() => setShowPasswordForm(false)}>取消</Button><Button htmlType="submit" className="primary" disabled={busy}>修改并重新登录</Button></div></Form></Modal>}
  </div>
}

function PageHeading({ eyebrow, title, intro, action }: { eyebrow: string; title: string; intro: string; action?: React.ReactNode }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{intro}</p></div>{action}</div> }
function Empty({ title, body }: { title: string; body: string }) { return <AntEmpty description={<><strong>{title}</strong><p>{body}</p></>}/> }
function WorkflowList({ workflows, hotspots, onOpen }: { workflows: Workflow[]; hotspots: Hotspot[]; onOpen: (id: string) => void }) { return <Table rowKey="id" dataSource={workflows} pagination={{ pageSize: 10, hideOnSinglePage: true }} locale={{ emptyText: '还没有工作流，请从热点大厅开始创作。' }} columns={[{ title: '工作流', render: (_, w) => hotspots.find(h => h.id === w.hotspot_id)?.title || '工作流' }, { title: '创建时间', render: (_, w) => formatDate(w.created_at) }, { title: '操作', render: (_, w) => <Button type="link" onClick={() => onOpen(w.id)}>打开</Button> }]}/> }
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <AntModal title={title} open onCancel={onClose} footer={null} destroyOnHidden>{children}</AntModal> }

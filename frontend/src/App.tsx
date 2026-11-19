import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type AgentEvent, type Hotspot, type Product, type ProductGroup, type User, type Workflow } from './api'
import AdminPanel from './features/admin/AdminPanel'

type Page = 'overview' | 'hotspots' | 'workflows' | 'products' | 'agents' | 'logs' | 'settings'
const menu: { key: Page; label: string; mark: string }[] = [
  { key: 'overview', label: '总览', mark: '◫' },
  { key: 'hotspots', label: '热点信息大厅', mark: '⌁' },
  { key: 'workflows', label: '工作流', mark: '◇' },
  { key: 'products', label: '产品库', mark: '▣' },
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
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span></span><span></span><span></span></div><div><strong>loom</strong><small>CONTENT STUDIO</small></div></div>
      <div className="workspace-label">工作空间 <span>01</span></div>
      <nav>{visibleMenu.map(item => <button key={item.key} className={`nav-item ${page === item.key ? 'active' : ''}`} onClick={() => setPage(item.key)}><span className="nav-mark">{item.mark}</span>{item.label}{item.key === 'hotspots' && <em>{hotspots.length}</em>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-rule"/><p>当前阶段</p><strong>基础平台搭建</strong><small>模型与采集来源待配置</small></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">内容工作台 <span>/</span> {menu.find(x => x.key === page)?.label}</div><div className="top-actions"><span className={`connection ${connected ? 'online' : ''}`}><i/>{connected ? 'API 已连接' : 'API 未连接'}</span><span className="signed-user">{user.username}</span><button className="text-link" onClick={() => setShowPasswordForm(true)}>修改密码</button><button className="ghost logout" onClick={() => void logout()}>退出</button></div></header>
      {error && <div className="error-banner"><span>{error}</span><button onClick={() => { setError(''); void refresh() }}>重试</button></div>}
      <div className="content">
        {page === 'overview' && <><div className="eyebrow">LOOM / OVERVIEW</div><div className="heading-row"><div><h1>让好内容<br/><em>开始流动。</em></h1><p className="lead">从种草灵感到可发布的内容，保持每一步都可看、可改、可追溯。</p></div><div className="edition">BUILD 001<span>工作台预览</span></div></div><div className="quick-grid"><button className="quick-card dark" onClick={() => { setPage('hotspots'); setShowHotspotForm(true) }}><div className="quick-top"><span>01 / 从内容开始</span><b>↗</b></div><h2>添加一条灵感</h2><p>粘贴你找到的文章或视频，开始创建工作流。</p><div className="quick-foot">手动导入 · 立即可用</div></button><button className="quick-card" onClick={() => setPage('products')}><div className="quick-top"><span>02 / 准备产品</span><b>↗</b></div><h2>建立产品资料</h2><p>产品信息会成为后续推荐与创作的事实依据。</p><div className="quick-foot">已录入 {products.length} 个产品</div></button></div><div className="section-title"><h3>流程概览</h3><span>从发现到定稿</span></div><div className="stage-track">{stages.map((stage, i) => <div className="stage" key={stage}><span>{String(i + 1).padStart(2, '0')}</span><strong>{stage}</strong>{i < stages.length - 1 && <b>→</b>}</div>)}</div><div className="section-title lower"><h3>最近工作流</h3><button className="text-link" onClick={() => setPage('workflows')}>查看全部 →</button></div><WorkflowList workflows={workflows.slice(0, 3)} hotspots={hotspots} onOpen={id => { setSelectedWorkflow(id); setPage('workflows') }}/></>}
        {page === 'hotspots' && <><PageHeading eyebrow="DISCOVERY / 01" title="热点信息大厅" intro="收集高表现种草作品。当前来源为手动导入，自动采集接入后会在这里显示。" action={<button className="primary" onClick={() => setShowHotspotForm(true)}>＋ 添加内容</button>}/><div className="notice"><span>◉</span><div><strong>采集来源尚未接入</strong><p>列表中的内容由团队手动提交，不会显示为自动抓取的热点。</p></div></div><div className="list-header"><span>内容列表</span><small>{hotspots.length} 条内容</small></div>{hotspots.length ? <div className="hotspot-grid">{hotspots.map(h => <article className="hotspot-card" key={h.id}><div className="card-meta"><span className="pill">{badge(h.content_type)}</span><span>手动导入</span></div><h3>{h.title}</h3><p>{h.summary || '暂无摘要。进入工作流前请补充有权使用的原始素材。'}</p><div className="card-bottom"><small>{formatDate(h.created_at)}</small><button onClick={() => void startWorkflow(h.id)} disabled={busy}>开始创作 ↗</button></div></article>)}</div> : <Empty title="还没有热点内容" body="添加你找到的种草图文或视频，作为第一条创作素材。"/>}</>}
        {page === 'workflows' && <><PageHeading eyebrow="WORKFLOWS / 02" title="工作流" intro="每一次创作都保留节点、版本和执行记录。"/>{selected ? <div className="workflow-detail"><button className="back" onClick={() => setSelectedWorkflow(null)}>← 返回列表</button><div className="detail-head"><div><span className="pill">等待素材确认</span><h2>{selectedHotspot?.title || '未命名工作流'}</h2><p>工作流 ID · {selected.id.slice(0, 12)}</p></div><button className="ghost" disabled title="模型配置后开放">运行 Agent</button></div><div className="detail-grid"><div><h3>流程节点</h3><div className="vertical-stages">{stages.map((stage, i) => <div className={i === 0 ? 'current' : ''} key={stage}><span>{String(i + 1).padStart(2, '0')}</span><strong>{stage}</strong><small>{i === 0 ? '等待素材与模型配置' : '尚未开始'}</small></div>)}</div></div><div><h3>Agent 执行过程</h3><div className="event-list">{events.map(e => <div className="event" key={e.id}><span className="event-dot"/><div><small>{formatDate(e.created_at)} · {e.agent_type}</small><strong>{e.title}</strong><p>{e.summary}</p></div></div>)}</div><div className="process-note">接入模型后，这里会实时展示依据、工具调用、草稿版本和修订摘要。</div></div></div></div> : <WorkflowList workflows={workflows} hotspots={hotspots} onOpen={setSelectedWorkflow}/>}</>}
        {page === 'products' && <><PageHeading eyebrow="CATALOG / 03" title="产品库" intro="这里只显示你有权查看的产品。产品资料是后续推荐与创作的事实依据。" action={['admin', 'product_manager'].includes(user.role) ? <button className="primary" onClick={() => setShowProductForm(true)}>＋ 新建产品</button> : undefined}/><div className="list-header"><span>可见产品</span><small>{products.length} 个 SKU</small></div>{products.length ? <div className="product-list">{products.map(p => <div className="product-row" key={p.id}><div className="product-icon">▣</div><div className="product-main"><strong>{p.name}</strong><small>{p.sku} · {p.category}</small></div>{user.role === 'admin' ? <select className="product-group-select" aria-label={`${p.name}的产品分组`} value={p.group_id || ''} onChange={e => { if (e.target.value) void assignProductGroup(p.id, e.target.value) }}><option value="">未分组</option>{groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select> : <span className="status-pill">{groups.find(g => g.id === p.group_id)?.name || '未分组'}</span>}<span className="product-date">{formatDate(p.created_at)}</span></div>)}</div> : <Empty title="暂无可见产品" body="请联系管理员授权产品分组，或由产品管理员录入产品。"/>}</>}
        {page === 'agents' && <><PageHeading eyebrow="AGENTS / 04" title="Agent 配置" intro="每个 Agent 都会拥有自己的模型、Skill、工具权限和执行记录。"/><div className="agent-grid">{['热点采集','热点分析','产品推荐','文章创作','美工设计','视频编剧','分镜设计','内容审核'].map((name, i) => <div className="agent-card" key={name}><span className="agent-number">{String(i + 1).padStart(2, '0')}</span><div className="agent-glyph">✳</div><h3>{name}</h3><p>{i < 3 ? '数据与判断' : i < 7 ? '内容创作' : '质量检查'}</p><span className="status-pill muted">待配置</span></div>)}</div><div className="notice spacer"><span>◉</span><div><strong>模型连接尚未配置</strong><p>Agent 运行接口目前会明确返回未配置状态，不会伪造执行结果。</p></div></div></>}
        {page === 'logs' && <><PageHeading eyebrow="ACTIVITY / 05" title="运行日志" intro="查看工作流创建与 Agent 执行过程。"/><div className="list-header"><span>事件</span><small>按工作流查看</small></div><WorkflowList workflows={workflows} hotspots={hotspots} onOpen={id => { setSelectedWorkflow(id); setPage('workflows') }}/></>}
        {page === 'settings' && user.role === 'admin' && <><PageHeading eyebrow="ACCESS / 06" title="成员与授权" intro="创建成员、建立产品分组，并决定各成员可见的产品范围。"/><AdminPanel currentUserId={user.id} onGroupsChanged={() => { void refresh() }}/></>}
      </div>
    </main>
    {showProductForm && <Modal title="新建产品" onClose={() => setShowProductForm(false)}><form onSubmit={submitProduct} className="form"><label>产品分组<select required value={productDraft.group_id} onChange={e => setProductDraft({ ...productDraft, group_id: e.target.value })}><option value="">选择分组</option>{groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>{!groups.length && <p className="form-help">请先由管理员在“成员与授权”中创建产品分组。</p>}<label>产品名称<input required value={productDraft.name} onChange={e => setProductDraft({ ...productDraft, name: e.target.value })} placeholder="例如：开放式蓝牙耳机"/></label><label>SKU<input required value={productDraft.sku} onChange={e => setProductDraft({ ...productDraft, sku: e.target.value })} placeholder="例如：EAR-001"/></label><label>品类<input required value={productDraft.category} onChange={e => setProductDraft({ ...productDraft, category: e.target.value })} placeholder="例如：耳机"/></label><label>产品描述<textarea value={productDraft.description} onChange={e => setProductDraft({ ...productDraft, description: e.target.value })} placeholder="填写已核实的产品资料"/></label><div className="form-actions"><button type="button" className="ghost" onClick={() => setShowProductForm(false)}>取消</button><button className="primary" disabled={busy || !productDraft.group_id}>保存产品</button></div></form></Modal>}
    {showHotspotForm && <Modal title="添加内容灵感" onClose={() => setShowHotspotForm(false)}><form onSubmit={submitHotspot} className="form"><label>标题<input required value={hotspotDraft.title} onChange={e => setHotspotDraft({ ...hotspotDraft, title: e.target.value })} placeholder="这条内容讲了什么？"/></label><label>内容类型<select value={hotspotDraft.content_type} onChange={e => setHotspotDraft({ ...hotspotDraft, content_type: e.target.value as Hotspot['content_type'] })}><option value="article">图文</option><option value="video">视频</option><option value="text">纯文字</option></select></label><label>原文链接<input value={hotspotDraft.source_url} onChange={e => setHotspotDraft({ ...hotspotDraft, source_url: e.target.value })} placeholder="https://..."/></label><label>摘要<textarea value={hotspotDraft.summary} onChange={e => setHotspotDraft({ ...hotspotDraft, summary: e.target.value })} placeholder="写下值得借鉴的角度；生成前仍需提供可用素材"/></label><div className="form-actions"><button type="button" className="ghost" onClick={() => setShowHotspotForm(false)}>取消</button><button className="primary" disabled={busy}>添加内容</button></div></form></Modal>}
    {showPasswordForm && <Modal title="修改密码" onClose={() => setShowPasswordForm(false)}><form onSubmit={changePassword} className="form"><label>当前密码<input type="password" autoComplete="current-password" required value={passwordDraft.current_password} onChange={e => setPasswordDraft({ ...passwordDraft, current_password: e.target.value })}/></label><label>新密码<input type="password" autoComplete="new-password" required minLength={12} value={passwordDraft.new_password} onChange={e => setPasswordDraft({ ...passwordDraft, new_password: e.target.value })} placeholder="至少 12 位"/></label><div className="form-actions"><button type="button" className="ghost" onClick={() => setShowPasswordForm(false)}>取消</button><button className="primary" disabled={busy}>修改并重新登录</button></div></form></Modal>}
  </div>
}

function PageHeading({ eyebrow, title, intro, action }: { eyebrow: string; title: string; intro: string; action?: React.ReactNode }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{intro}</p></div>{action}</div> }
function Empty({ title, body }: { title: string; body: string }) { return <div className="empty"><div>✳</div><h3>{title}</h3><p>{body}</p></div> }
function WorkflowList({ workflows, hotspots, onOpen }: { workflows: Workflow[]; hotspots: Hotspot[]; onOpen: (id: string) => void }) { return workflows.length ? <div className="workflow-list">{workflows.map(w => <button key={w.id} onClick={() => onOpen(w.id)}><span className="workflow-symbol">◇</span><span><strong>{hotspots.find(h => h.id === w.hotspot_id)?.title || '工作流'}</strong><small>{formatDate(w.created_at)} · 等待素材确认</small></span><b>↗</b></button>)}</div> : <Empty title="还没有工作流" body="从热点大厅选择一条内容，开始第一条创作流程。"/> }
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><div className="modal"><div className="modal-head"><h2>{title}</h2><button onClick={onClose} aria-label="关闭">×</button></div>{children}</div></div> }

function LoginScreen({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { await onLogin(username, password) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="login-page"><div className="login-brand"><div className="brand-mark"><span/><span/><span/></div><div><strong>loom</strong><small>CONTENT STUDIO</small></div></div><div className="login-card"><div className="eyebrow">WORKSPACE ACCESS</div><h1>登录内容工作台</h1><p>使用管理员为你创建的账号进入团队工作空间。</p><form className="form" onSubmit={submit}><label>用户名<input autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} placeholder="输入用户名"/></label><label>密码<input autoComplete="current-password" required type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="输入密码"/></label>{error && <div className="login-error" role="alert">{error}</div>}<button className="primary" disabled={busy}>{busy ? '正在登录…' : '登录'}</button></form></div><small className="login-footer">LOOM · INTERNAL CONTENT WORKSPACE</small></div>
}


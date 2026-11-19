import { useEffect, useState } from 'react'
import { api, type ProductGroup, type User } from '../../api'

const roleLabels: Record<User['role'], string> = {
  admin: '平台管理员', product_manager: '产品管理员', creator: '内容运营',
  reviewer: '审核人员', viewer: '只读成员',
}

export default function AdminPanel({ onGroupsChanged, currentUserId }: { onGroupsChanged: () => void; currentUserId: string }) {
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<ProductGroup[]>([])
  const [grants, setGrants] = useState<User[]>([])
  const [selectedGroup, setSelectedGroup] = useState('')
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<User['role']>('creator')
  const [grantUser, setGrantUser] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function refresh() {
    const [nextUsers, nextGroups] = await Promise.all([api.users(), api.groups()])
    setUsers(nextUsers); setGroups(nextGroups)
    setSelectedGroup(current => current || nextGroups[0]?.id || '')
  }
  useEffect(() => { void refresh().catch(e => setMessage((e as Error).message)) }, [])
  useEffect(() => {
    if (selectedGroup) void api.groupGrants(selectedGroup).then(setGrants).catch(e => setMessage((e as Error).message))
    else setGrants([])
  }, [selectedGroup])

  async function run(action: () => Promise<unknown>, success: string): Promise<boolean> {
    setBusy(true); setMessage('')
    try {
      await action(); await refresh()
      if (selectedGroup) setGrants(await api.groupGrants(selectedGroup))
      onGroupsChanged(); setMessage(success); return true
    } catch (e) { setMessage((e as Error).message); return false }
    finally { setBusy(false) }
  }

  return <div className="admin-layout">
    <div className="admin-panel">
      <h3>成员账号</h3><p>管理员创建账号并分配角色。新成员需获得产品分组授权，才能看到组内产品。</p>
      <form className="form" onSubmit={e => { e.preventDefault(); void run(() => api.createUser({ username, password, role }), '账号已创建').then(ok => { if (ok) { setUsername(''); setPassword('') } }) }}>
        <label>用户名<input required minLength={3} value={username} onChange={e => setUsername(e.target.value)} placeholder="例如 content_01"/></label>
        <label>初始密码<input required minLength={12} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="至少 12 位"/></label>
        <label>角色<select value={role} onChange={e => setRole(e.target.value as User['role'])}>{Object.entries(roleLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <button className="primary" disabled={busy}>创建账号</button>
      </form>
      <div className="admin-list">{users.map(user => <div key={user.id}><strong>{user.username}</strong><small>{roleLabels[user.role]} · {user.is_active ? '启用' : '停用'}</small><button className="text-link" disabled={busy || user.id === currentUserId} onClick={() => void run(() => api.setUserActive(user.id, !user.is_active), user.is_active ? '账号已停用' : '账号已启用')}>{user.is_active ? '停用' : '启用'}</button></div>)}</div>
    </div>
    <div className="admin-panel">
      <h3>产品分组与授权</h3><p>产品必须放入分组。管理员可决定每位成员能查看哪些分组。</p>
      <form className="form admin-inline" onSubmit={e => { e.preventDefault(); void run(() => api.createGroup(name), '分组已创建').then(ok => { if (ok) setName('') }) }}>
        <label>新分组名称<input required value={name} onChange={e => setName(e.target.value)} placeholder="例如 3C / 耳机"/></label><button className="primary" disabled={busy}>新增分组</button>
      </form>
      <label className="admin-select-label">当前分组<select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value)}>{groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
      {selectedGroup && <><form className="form admin-inline" onSubmit={e => { e.preventDefault(); void run(() => api.grantGroup(selectedGroup, grantUser), '授权已更新').then(ok => { if (ok) setGrantUser('') }) }}>
        <label>授权成员<select required value={grantUser} onChange={e => setGrantUser(e.target.value)}><option value="">选择成员</option>{users.filter(user => user.role !== 'admin' && !grants.some(grant => grant.id === user.id)).map(user => <option key={user.id} value={user.id}>{user.username}</option>)}</select></label><button className="primary" disabled={busy || !grantUser}>授予访问</button>
      </form><div className="admin-list"><strong className="admin-list-title">已授权成员</strong>{grants.length ? grants.map(user => <div key={user.id}><strong>{user.username}</strong><button className="text-link" disabled={busy} onClick={() => void run(() => api.revokeGroup(selectedGroup, user.id), '授权已撤销')}>撤销</button></div>) : <small>暂无成员获得授权</small>}</div></>}
    </div>
    {message && <div className="admin-message" role="status">{message}</div>}
  </div>
}

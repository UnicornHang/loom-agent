import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag } from 'antd'
import { api, type SkillVersion } from '../../api'

const agentOptions = ['collector', 'analyst', 'recommender', 'writer', 'designer', 'screenwriter', 'storyboard', 'reviewer'].map((value, i) => ({ value, label: ['热点采集', '热点分析', '产品推荐', '文章创作', '美工', '编剧', '分镜', '审核'][i] }))
export default function SkillLibrary() {
  const [rows, setRows] = useState<SkillVersion[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [form] = Form.useForm()
  async function refresh() { setRows(await api.skills()) }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [])
  async function action(fn: () => Promise<unknown>) { setBusy(true); setError(''); try { await fn(); await refresh() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  function edit(row?: SkillVersion) { form.resetFields(); form.setFieldsValue(row ? { ...row, base_version: Math.max(...rows.filter(r => r.skill_key === row.skill_key).map(r => r.version)) } : { base_version: 0, manifest: { agents: ['writer'], industries: [], variables: [] } }); setOpen(true) }
  return <Card title="可复用 Skill 版本库" extra={<Button type="primary" onClick={() => edit()}>新建 Skill</Button>}>
    <Alert type="info" title="发布表示方法模板可被绑定，不授予工具权限、不执行脚本。Agent 保存时锁定引用正文；正式调用前仍需测试并发布 Agent 配置。" />
    {error && <Alert type="error" title={error} />}
    <Table rowKey="id" dataSource={rows} columns={[{ title: '名称', render: (_, row) => row.manifest.name }, { title: '标识', dataIndex: 'skill_key' }, { title: '版本', dataIndex: 'version' }, { title: '状态', render: (_, row) => <Tag>{row.status === 'published' ? '已发布模板' : '草稿'}</Tag> }, { title: '操作', render: (_, row) => <Space><Button disabled={busy} onClick={() => edit(row)}>基于此版编辑</Button><Button disabled={busy || row.status === 'published'} onClick={() => action(() => api.publishSkill(row.id))}>校验并发布模板</Button></Space> }]} />
    <Modal title="保存 Skill 新版本" open={open} onCancel={() => { if (!busy) setOpen(false) }} footer={null}>
      <Form form={form} layout="vertical" onFinish={values => action(async () => { await api.saveSkill(values); setOpen(false) })}>
        <Form.Item name="base_version" hidden><Input /></Form.Item>
        <Form.Item name="skill_key" label="唯一标识（小写英文、数字、连字符）" rules={[{ required: true }, { pattern: /^[a-z][a-z0-9_-]{1,99}$/ }]}><Input /></Form.Item>
        <Form.Item name={['manifest', 'name']} label="名称" rules={[{ required: true }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name={['manifest', 'description']} label="用途说明" rules={[{ required: true }]}><Input.TextArea maxLength={2000} /></Form.Item>
        <Form.Item name={['manifest', 'agents']} label="适用 Agent" rules={[{ required: true }]}><Select mode="multiple" options={agentOptions} /></Form.Item>
        <Form.Item name={['manifest', 'industries']} label="适用行业（空白表示通用）"><Select mode="tags" /></Form.Item>
        <Form.Item name={['manifest', 'variables']} label="声明变量名"><Select mode="tags" /></Form.Item>
        <Form.Item name="content" label="SKILL.md 正文" rules={[{ required: true, whitespace: true }]}><Input.TextArea rows={10} maxLength={30000} /></Form.Item>
        <Button loading={busy} type="primary" htmlType="submit">保存新版本</Button>
      </Form>
    </Modal>
  </Card>
}

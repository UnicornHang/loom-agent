import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag } from 'antd'
import { api, type SourceConfig, type SourceInput, type CollectionRun } from '../../api'

export default function SourceSettings() {
  const [rows, setRows] = useState<SourceConfig[]>([])
  const [logs, setLogs] = useState<CollectionRun[]>([])
  const [selected, setSelected] = useState<SourceConfig | null>(null)
  const [editing, setEditing] = useState<SourceConfig | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [form] = Form.useForm<SourceInput>()
  async function refresh() { setRows(await api.sources()) }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [])
  async function action(fn: () => Promise<unknown>) { setBusy(true); setError(''); try { await fn(); await refresh() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  function edit(row: SourceConfig | null) { setEditing(row); form.resetFields(); form.setFieldsValue(row || { name: '', adapter: 'douyin_official', industry: '3C', keywords: [], interval_minutes: 60, enabled: false, authorization_note: '', revision: 0 }); setOpen(true) }
  return <Space orientation="vertical" style={{ width: '100%' }}>
    <Alert type="warning" showIcon title="尚未取得外部来源授权。当前支持配置与定时预检，不发起平台请求，不会生成自动采集的热点数据。" />
    {error && <Alert type="error" title={error} />}
    <Card title="采集来源" extra={<Button type="primary" onClick={() => edit(null)}>添加来源</Button>}>
      <Table rowKey="id" dataSource={rows} scroll={{ x: 800 }} columns={[
        { title: '名称', dataIndex: 'name' }, { title: '行业', dataIndex: 'industry' },
        { title: '关键词', render: (_, row) => row.keywords.join('、') || '全品类' },
        { title: '间隔', render: (_, row) => `${row.interval_minutes} 分钟` },
        { title: '调度', render: (_, row) => <Tag>{row.enabled ? '定时预检中' : '已停用'}</Tag> },
        { title: '下次预检', render: (_, row) => row.enabled ? new Date(row.next_run_at).toLocaleString() : '—' },
        { title: '操作', render: (_, row) => <Space><Button disabled={busy} onClick={() => edit(row)}>编辑</Button><Button disabled={busy} onClick={() => action(async () => { await api.runSource(row.id); setLogs(await api.sourceRuns(row.id)); setSelected(row) })}>立即预检</Button><Button onClick={() => action(async () => { setLogs(await api.sourceRuns(row.id)); setSelected(row) })}>日志</Button></Space> },
      ]} />
    </Card>
    {selected && <Card title={`${selected.name} · 最近执行记录`}><Table rowKey="id" dataSource={logs} columns={[{ title: '时间', render: (_, row) => new Date(row.created_at).toLocaleString() }, { title: '配置版本', dataIndex: 'source_revision' }, { title: '触发方式', render: (_, row) => row.trigger === 'scheduled' ? '定时' : '手动' }, { title: '结果', render: () => '等待授权与适配器' }, { title: '说明', dataIndex: 'summary' }]} /></Card>}
    <Modal title={editing ? '编辑来源' : '添加来源'} open={open} onCancel={() => { if (!busy) setOpen(false) }} footer={null}>
      <Form form={form} layout="vertical" onFinish={values => action(async () => { await api.saveSource({ ...values, revision: editing?.revision || 0 }, editing?.id); setOpen(false) })}>
        <Form.Item name="name" label="来源名称" rules={[{ required: true, whitespace: true }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="adapter" label="计划接入方式" rules={[{ required: true }]}><Select options={[{ value: 'douyin_official', label: '抖音官方接口（待接入）' }, { value: 'licensed_feed', label: '授权内容接口 / RSS（待接入）' }, { value: 'custom_authorized', label: '自建授权适配器（待接入）' }]} /></Form.Item>
        <Form.Item name="industry" label="行业" rules={[{ required: true, whitespace: true }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="keywords" label="品类 / 关键词（空白表示全品类）"><Select mode="tags" tokenSeparators={[',', '，']} /></Form.Item>
        <Form.Item name="interval_minutes" label="调度间隔（分钟）" rules={[{ required: true }]}><InputNumber min={15} max={1440} /></Form.Item>
        <Form.Item name="authorization_note" label="授权范围与待办说明"><Input.TextArea rows={4} maxLength={3000} /></Form.Item>
        <Form.Item name="enabled" label="启用定时预检" valuePropName="checked"><Switch /></Form.Item>
        <Button htmlType="submit" type="primary" loading={busy}>保存来源</Button>
      </Form>
    </Modal>
  </Space>
}

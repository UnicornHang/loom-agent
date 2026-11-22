import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag, Typography } from 'antd'
import { api, type MCPServer } from '../../api'

export default function MCPSettings() {
  const [rows, setRows] = useState<MCPServer[]>([])
  const [editing, setEditing] = useState<MCPServer | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<MCPServer | null>(null)
  const [form] = Form.useForm()
  async function refresh() { setRows(await api.mcpServers()) }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [])
  async function action(fn: () => Promise<unknown>) { setBusy(true); setError(''); try { await fn(); await refresh() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  function edit(row: MCPServer | null) { setEditing(row); form.resetFields(); form.setFieldsValue(row ? { name: row.name, endpoint: row.endpoint, timeout_seconds: row.timeout_seconds, data_scope: row.data_scope, enabled: row.enabled, token: '', clear_token: false } : { timeout_seconds: 15, data_scope: 'none', enabled: false }); setOpen(true) }
  return <Space orientation="vertical" style={{ width: '100%' }}>
    <Alert type="info" title="支持公网 HTTPS Streamable HTTP 服务登记、初始化与工具发现（协议 2025-06-18）。当前不执行外部工具；数据范围为后续授权配置，不会因发现工具自动开放权限。" />
    {error && <Alert type="error" title={error} />}
    <Card title="MCP 服务管理" extra={<Button type="primary" onClick={() => edit(null)}>登记服务</Button>}>
      <Table rowKey="id" dataSource={rows} columns={[{ title: '名称', dataIndex: 'name' }, { title: '地址', dataIndex: 'endpoint' }, { title: '凭据', render: (_, row) => row.has_token ? '已加密保存' : '未配置' }, { title: '工具发现', render: (_, row) => <Tag>{row.tested_revision === row.revision ? `${row.tools.length} 个工具` : '当前版本未测试'}</Tag> }, { title: '操作', render: (_, row) => <Space><Button disabled={busy} onClick={() => edit(row)}>编辑</Button><Button disabled={busy || !row.enabled} onClick={() => Modal.confirm({ title: '连接 MCP 服务并发现工具？', content: '发送初始化与工具列表请求，使用已保存凭据，不传输产品或稿件，不执行工具。', onOk: () => action(async () => setSelected(await api.discoverMCP(row.id))) })}>测试并发现工具</Button><Button onClick={() => setSelected(row)}>工具清单</Button></Space> }]} />
    </Card>
    {selected && <Card title={`${selected.name} · 只读工具清单`}>{selected.tools.map(tool => <Card key={tool.name} size="small" title={tool.name}><Typography.Paragraph>{tool.description}</Typography.Paragraph><Typography.Paragraph code>{JSON.stringify(tool.inputSchema)}</Typography.Paragraph></Card>)}</Card>}
    <Modal title="MCP 服务配置" open={open} onCancel={() => { if (!busy) setOpen(false) }} footer={null}>
      <Form form={form} layout="vertical" onFinish={values => action(async () => { await api.saveMCP({ ...values, revision: editing?.revision || 0 }, editing?.id); setSelected(null); setOpen(false) })}>
        <Form.Item name="name" label="服务名称" rules={[{ required: true, whitespace: true }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="endpoint" label="MCP HTTPS 地址" rules={[{ required: true }, { type: 'url' }]}><Input maxLength={500} /></Form.Item>
        <Form.Item name="token" label="Bearer Token（留空保留原凭据）"><Input.Password autoComplete="new-password" maxLength={4096} /></Form.Item>
        <Form.Item name="clear_token" label="清除已有凭据" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="timeout_seconds" label="单请求超时（秒）" rules={[{ required: true }]}><InputNumber min={1} max={30} /></Form.Item>
        <Form.Item name="data_scope" label="计划允许的数据范围"><Select options={[{ value: 'none', label: '不允许业务数据出站' }, { value: 'public_only', label: '公开资料' }, { value: 'authorized_product', label: '授权产品资料（待执行网关接入）' }]} /></Form.Item>
        <Form.Item name="enabled" label="启用服务登记" valuePropName="checked"><Switch /></Form.Item>
        <Button htmlType="submit" type="primary" loading={busy}>保存配置</Button>
      </Form>
    </Modal>
  </Space>
}

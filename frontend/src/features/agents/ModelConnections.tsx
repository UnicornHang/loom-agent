import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Select, Modal, Space, Switch, Table, Tag } from 'antd'
import { api, type ModelConnection, type ModelConnectionInput } from '../../api'

export default function ModelConnections() {
  const [rows, setRows] = useState<ModelConnection[]>([])
  const [editing, setEditing] = useState<ModelConnection | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [form] = Form.useForm<ModelConnectionInput>()
  async function refresh() { setRows(await api.modelConnections()) }
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [])
  function edit(row: ModelConnection | null) {
    setEditing(row); form.resetFields()
    form.setFieldsValue(row ? { ...row, api_key: '' } : { enabled: false, options: { capability: 'text', currency: 'CNY', input_price: 0, output_price: 0 } })
    setError(''); setOpen(true)
  }
  async function save(values: ModelConnectionInput) {
    setBusy(true); setError('')
    try { await api.saveModelConnection(values, editing?.id); setOpen(false); form.resetFields(); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败') }
    finally { setBusy(false) }
  }
  return <Card title="通用模型连接" extra={<Button type="primary" onClick={() => edit(null)}>添加连接</Button>}>
    <Space orientation="vertical" style={{ width: '100%' }}>
      <Alert type="info" showIcon title="配置 OpenAI 兼容接口。真实文本测试在 Agent 管理中执行；图片、视觉和语音适配仍待接入。计价按每百万 Token 填写。" />
      {error && !open && <Alert type="error" title={error} />}
      <Table rowKey="id" dataSource={rows} pagination={{ pageSize: 5 }} scroll={{ x: 650 }} columns={[
        { title: '名称', dataIndex: 'name' }, { title: '模型', dataIndex: 'model_name' },
        { title: 'API 地址', dataIndex: 'base_url' },
        { title: '状态', render: (_, row) => <Tag color={row.enabled ? 'blue' : 'default'}>{row.enabled ? '已启用 · 未验证' : '已停用'}</Tag> },
        { title: '操作', render: (_, row) => <Button onClick={() => edit(row)}>编辑</Button> },
      ]} />
    </Space>
    <Modal title={editing ? '编辑模型连接' : '添加模型连接'} open={open} onCancel={() => { if (!busy) { setOpen(false); form.resetFields() } }} footer={null} closable={!busy} maskClosable={!busy}>
      <Form form={form} layout="vertical" onFinish={save}>
        {error && <Alert type="error" title={error} />}
        <Form.Item name="name" label="连接名称" rules={[{ required: true, whitespace: true }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="base_url" label="API 基础地址（HTTPS）" rules={[{ required: true }, { type: 'url' }]}><Input placeholder="https://供应商域名/v1" maxLength={500} /></Form.Item>
        <Form.Item name="model_name" label="模型名称" rules={[{ required: true, whitespace: true }]}><Input maxLength={200} /></Form.Item>
        <Form.Item name={['options', 'capability']} label="能力类型"><Select options={[{ value: 'text', label: '文本' }, { value: 'embedding', label: '嵌入 / 向量' }, { value: 'vision', label: '视觉（待接入）' }, { value: 'image', label: '图片（待接入）' }, { value: 'audio', label: '语音（待接入）' }]} /></Form.Item>
        <Form.Item name={['options', 'currency']} label="计价币种"><Select options={[{ value: 'CNY', label: '人民币' }, { value: 'USD', label: '美元' }]} /></Form.Item>
        <Form.Item name={['options', 'input_price']} label="输入价格 / 百万 Token"><InputNumber min={0} max={100000} /></Form.Item>
        <Form.Item name={['options', 'output_price']} label="输出价格 / 百万 Token"><InputNumber min={0} max={100000} /></Form.Item>
        <Form.Item name="api_key" label={editing ? '替换 API Key（留空保留原密钥）' : 'API Key'} rules={editing ? [] : [{ required: true, whitespace: true }]}><Input.Password autoComplete="new-password" maxLength={4096} /></Form.Item>
        <Form.Item name="enabled" label="启用连接" valuePropName="checked"><Switch /></Form.Item>
        <Button htmlType="submit" type="primary" loading={busy}>保存连接</Button>
      </Form>
    </Modal>
  </Card>
}

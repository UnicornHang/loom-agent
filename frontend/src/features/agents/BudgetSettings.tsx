import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, InputNumber, Select, Table } from 'antd'
import { api } from '../../api'

export default function BudgetSettings() {
  const [form] = Form.useForm()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [rows, setRows] = useState<{ id: string; day: string; amount: number; status: string }[]>([])
  async function load() { const [policy, usage] = await Promise.all([api.budget(), api.usage()]); form.setFieldsValue(policy); setRows(usage) }
  useEffect(() => { load().catch(e => setError(e.message)) }, [])
  async function save(values: { daily_limit: number; currency: string }) {
    setBusy(true); setError('')
    try { await api.saveBudget(values); await load() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <Card title="每日 AI 预算">
    <Alert type="info" title="北京时间自然日统计。未配置预算时不启动计费请求；失败或用量未知的请求暂保留额度，避免重复扣费。" />
    {error && <Alert type="error" title={error} />}
    <Form form={form} layout="vertical" onFinish={save}>
      <Form.Item name="daily_limit" label="每日上限" rules={[{ required: true }]}><InputNumber min={0} max={1000} /></Form.Item>
      <Form.Item name="currency" label="币种" rules={[{ required: true }]}><Select options={[{ value: 'CNY', label: '人民币' }, { value: 'USD', label: '美元' }]} /></Form.Item>
      <Button type="primary" htmlType="submit" loading={busy}>保存预算</Button>
    </Form>
    <Table rowKey="id" dataSource={rows} columns={[{ title: '日期', dataIndex: 'day' }, { title: '金额', dataIndex: 'amount' }, { title: '记账状态', render: (_, row) => ({ reserved: '预留', settled: '按用量结算', estimated: '按预估保留', uncertain: '调用结果待核对' }[row.status] || row.status) }]} />
  </Card>
}

import { useEffect, useState } from 'react'
import { Alert, Card, Table } from 'antd'
import { api } from '../../api'

export default function AuditLog() {
  const [rows, setRows] = useState<{ id: string; user_id: string; action: string; object_id: string; summary: string; created_at: string }[]>([])
  const [error, setError] = useState('')
  useEffect(() => { api.auditEvents().then(setRows).catch(e => setError(e.message)) }, [])
  return <Card title="配置与预算审计（最近50条）">{error && <Alert type="error" title={error} />}<Table rowKey="id" dataSource={rows} columns={[{ title: '时间', render: (_, row) => new Date(row.created_at).toLocaleString() }, { title: '操作', dataIndex: 'action' }, { title: '操作人ID', dataIndex: 'user_id', ellipsis: true }, { title: '说明', dataIndex: 'summary' }]} /></Card>
}

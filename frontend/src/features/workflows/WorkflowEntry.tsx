import { useRef, useState } from 'react'
import { Alert, Avatar, Button, Card, Checkbox, Form, Input, Select, Space, Typography } from 'antd'
import { api } from '../../api'

export default function WorkflowEntry({ onCreated }: { onCreated: (id: string) => void }) {
  const key = useRef(crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(values: { title: string; material: string; content_type: string; source_url?: string; industry: string; rights_confirmed: boolean }) {
    setBusy(true); setError('')
    try { const result = await api.enterWorkflow({ ...values, source_url: values.source_url || null }, key.current); onCreated(result.id) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <Space orientation="vertical" style={{ width: '100%', maxWidth: 900 }}>
    <Card><Space align="start"><Avatar>✳</Avatar><div><Typography.Title level={4}>把你找到的种草内容交给工作流</Typography.Title><Typography.Paragraph>粘贴有权使用的文章正文或视频文字稿，说明内容类型。纯文字直接进入创作；图文和视频先选择产品。参考链接仅作记录，系统不会自动取得链接里的全文或视频。</Typography.Paragraph></div></Space></Card>
    <Card title="你的参考素材">
      {error && <Alert type="error" title={error} />}
      <Form layout="vertical" onFinish={submit} initialValues={{ content_type: 'article', industry: '3C', rights_confirmed: false }} disabled={busy}>
        <Form.Item name="title" label="这条创作的标题" rules={[{ required: true, whitespace: true }]}><Input maxLength={300} /></Form.Item>
        <Space wrap><Form.Item name="content_type" label="参考类型" rules={[{ required: true }]}><Select style={{ width: 200 }} options={[{ value: 'text', label: '纯文字文章' }, { value: 'article', label: '带图文章 / 笔记' }, { value: 'video', label: '视频（提交文字稿）' }]} /></Form.Item><Form.Item name="industry" label="行业" rules={[{ required: true, whitespace: true }]}><Input maxLength={100} /></Form.Item></Space>
        <Form.Item name="material" label="正文或视频文字稿" rules={[{ required: true, min: 20, whitespace: true }]}><Input.TextArea rows={10} maxLength={100000} placeholder="粘贴正文、视频台词及必要的画面描述……" /></Form.Item>
        <Form.Item name="source_url" label="原始参考链接（可选）" rules={[{ type: 'url' }]}><Input maxLength={1000} /></Form.Item>
        <Form.Item name="rights_confirmed" valuePropName="checked" rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error('请先确认素材使用权限')) }]}><Checkbox>我确认有权将上述素材用于本次分析与创作</Checkbox></Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>提交素材，开始工作流</Button>
      </Form>
    </Card>
  </Space>
}

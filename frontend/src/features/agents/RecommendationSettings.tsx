import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, InputNumber, Select } from 'antd'
import { api, type ModelConnection } from '../../api'

export default function RecommendationSettings() {
  const [form] = Form.useForm()
  const [models, setModels] = useState<ModelConnection[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { Promise.all([api.recommendationSettings(), api.modelConnections()]).then(([settings, rows]) => { form.setFieldsValue(settings); setModels(rows) }).catch(e => setError(e.message)) }, [])
  return <Card title="混合推荐检索配置">
    <Alert type="info" title="产品事实保存在业务数据库；嵌入向量仅用于召回。请先添加嵌入模型并设置输入价格，之后在产品编辑中建立索引；产品变更后旧索引自动失效。推荐评分还需要发布产品推荐 Agent 的文本配置。" />
    {error && <Alert type="error" title={error} />}{notice && <Alert type="success" title={notice} />}
    <Form form={form} layout="vertical" onFinish={async values => { setBusy(true); setError(''); setNotice(''); try { await api.saveRecommendationSettings(values); setNotice('推荐检索配置已保存') } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }}>
      <Form.Item name="embedding_connection_id" label="嵌入模型"><Select allowClear options={models.filter(m => m.options.capability === 'embedding').map(m => ({ value: m.id, label: `${m.name} / ${m.model_name}` }))} /></Form.Item>
      <Form.Item name="per_call_budget" label="单次索引或查询嵌入预算" rules={[{ required: true }]}><InputNumber min={0} max={100} /></Form.Item>
      <Button htmlType="submit" type="primary" loading={busy}>保存检索配置</Button>
    </Form>
  </Card>
}

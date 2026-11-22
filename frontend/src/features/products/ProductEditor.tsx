import { useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select } from 'antd'
import { api, type Product } from '../../api'

export default function ProductEditor({ product, onClose, onSaved }: { product: Product; onClose: () => void; onSaved: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function save(values: { name: string; category: string; description: string; status: string }) {
    setBusy(true); setError('')
    try { await api.updateProduct(product, values); onSaved(); onClose() }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <Modal title={`维护产品 · ${product.sku}`} open onCancel={() => { if (!busy) onClose() }} footer={null}>
    <Form layout="vertical" initialValues={product} onFinish={save}>
      {error && <Alert type="error" title={error} />}
      {notice && <Alert type="success" title={notice} />}
      <Form.Item name="name" label="产品名称" rules={[{ required: true, whitespace: true }]}><Input maxLength={200} /></Form.Item>
      <Form.Item name="category" label="品类" rules={[{ required: true, whitespace: true }]}><Input maxLength={100} /></Form.Item>
      <Form.Item name="description" label="产品描述与事实依据"><Input.TextArea rows={8} maxLength={30000} placeholder="填写核实后的规格、卖点、适用场景和来源资料；不要把推测作为产品事实。" /></Form.Item>
      <Form.Item name="status" label="状态" rules={[{ required: true }]}><Select options={[{ value: 'draft', label: '草稿' }, { value: 'active', label: '启用' }, { value: 'archived', label: '归档' }]} /></Form.Item>
      <Button type="primary" htmlType="submit" loading={busy}>保存产品</Button>
      <Button disabled={busy} onClick={() => Modal.confirm({ title: '更新已保存资料的推荐索引？', content: '将已保存的产品资料发送给管理员配置的嵌入模型，按预算计费。尚未保存的表单修改不参与索引。', onOk: async () => { setBusy(true); setError(''); try { const result = await api.indexProduct(product.id); setNotice(result.cached ? '索引已是当前版本' : '推荐索引已更新') } catch (e) { setError((e as Error).message) } finally { setBusy(false) } } })}>更新推荐索引</Button>
    </Form>
  </Modal>
}

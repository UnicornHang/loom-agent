import { Alert, Button, Card, Empty, Image, Popconfirm, Space, Upload, Typography } from 'antd'
import { useEffect, useState } from 'react'

export default function ProductImages({ productId, writable }: { productId: string; writable: boolean }) {
  const [images, setImages] = useState<{ id: string }[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const base = `/api/v1/products/${productId}/images`
  const csrf = () => document.cookie.split('; ').find(x => x.startsWith('loom_csrf='))?.slice(10) || ''
  async function refresh() {
    const response = await fetch(base)
    if (!response.ok) throw new Error('无法读取产品图片')
    setImages(await response.json())
  }
  useEffect(() => { void refresh().catch(e => setError(e.message)) }, [productId])
  async function mutate(method: string, suffix = '', file?: File) {
    setBusy(true); setError('')
    try {
      const response = await fetch(base + suffix, { method, headers: { 'X-CSRF-Token': csrf() }, body: file })
      if (!response.ok) { const data = await response.json(); throw new Error(data.detail || '操作失败') }
      await refresh()
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  return <Space orientation="vertical" style={{ width: '100%' }}><Typography.Paragraph>支持 JPG、PNG、WebP，单张最多 10 MB。图片仅对拥有该产品访问权限的成员开放。</Typography.Paragraph>{writable && <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} disabled={busy} beforeUpload={file => { void mutate('POST', '', file); return false }}><Button loading={busy}>上传产品图片</Button></Upload>}<Image.PreviewGroup><Space wrap>{images.map(image => <Card key={image.id} size="small"><Image src={`${base}/${image.id}`} alt="产品素材" width={180} height={150} style={{ objectFit: 'contain' }}/>{writable && <Popconfirm title="删除这张产品图片？" onConfirm={() => mutate('DELETE', `/${image.id}`)}><Button danger disabled={busy}>删除图片</Button></Popconfirm>}</Card>)}</Space></Image.PreviewGroup>{error && <Alert type="error" title={error}/>} {!images.length && <Empty description="暂无产品图片"/>}</Space>
}

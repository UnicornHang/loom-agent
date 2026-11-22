import { useEffect, useState } from 'react'
import { Alert, Button, Table, Tag } from 'antd'
import { api, type Artifact } from '../../api'

export default function ContentLibrary() {
  const [rows, setRows] = useState<Artifact[]>([])
  const [error, setError] = useState('')
  useEffect(() => { api.contents().then(setRows).catch(e => setError(e.message)) }, [])
  return <>{error && <Alert type="error" title={error} />}<Table rowKey="id" dataSource={rows} columns={[
    { title: '标题', dataIndex: 'title' }, { title: '版本', dataIndex: 'version' },
    { title: '类型', render: (_, row) => row.kind === 'storyboard' ? '分镜' : row.kind === 'script' ? '剧本' : '文章' },
    { title: '审核', render: (_, row) => <Tag>{row.review_status || '未审核'}</Tag> },
    { title: '来源', render: (_, row) => row.origin === 'manual' ? '人工编辑' : 'Agent 生成' },
    { title: '操作', render: (_, row) => <Button href={`/api/v1/contents/${row.id}/download`}>下载成果</Button> },
  ]} /></>
}

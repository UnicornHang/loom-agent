import { useState } from 'react'
import { Button, Card, Empty, Pagination, Tabs } from 'antd'
import type { Hotspot } from '../../api'

const sources: Record<string, string> = {
  douyin_hot_search: '抖音',
  weibo_hot_search: '微博',
  bilibili_popular: 'B站',
  xiaohongshu_hot_search: '小红书',
  manual: '手动导入',
}
const pageSize = 12
const dateFormat = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
})

export default function HotspotFeed({ hotspots, busy, onCreate }: {
  hotspots: Hotspot[]
  busy: boolean
  onCreate: (id: string) => void
}) {
  const [source, setSource] = useState('all')
  const [page, setPage] = useState(1)
  const counts = new Map<string, number>()
  hotspots.forEach(item => counts.set(item.source_kind, (counts.get(item.source_kind) || 0) + 1))
  const tabs = [
    { key: 'all', label: '全部', count: hotspots.length },
    ...Array.from(new Set([...Object.keys(sources), ...counts.keys()])).map(key => ({
      key, label: sources[key] || key, count: counts.get(key) || 0,
    })),
  ]
  const filtered = source === 'all' ? hotspots : hotspots.filter(item => item.source_kind === source)
  const current = Math.min(page, Math.max(1, Math.ceil(filtered.length / pageSize)))
  const visible = filtered.slice((current - 1) * pageSize, current * pageSize)
  const sourceLabel = tabs.find(tab => tab.key === source)?.label || '当前来源'

  return <section className="hotspot-feed" aria-label="按来源浏览热点">
    <Tabs activeKey={source} onChange={key => { setSource(key); setPage(1) }} items={tabs.map(tab => ({
      key: tab.key,
      label: <span className="hotspot-tab-label">{tab.label}<span className="hotspot-tab-count">{tab.count}</span></span>,
    }))} />
    <div className="list-header"><span>{sourceLabel} · 内容列表</span><small>{filtered.length} 条内容</small></div>
    {visible.length ? <>
      <div className="hotspot-grid">{visible.map(item => {
        const automatic = item.source_kind !== 'manual'
        return <Card className="hotspot-card" key={item.id}>
          <div className="card-meta">
            <span className="pill">{automatic ? (item.content_type === 'video' ? '视频线索' : '热搜话题') : item.content_type === 'video' ? '视频' : item.content_type === 'article' ? '图文' : '纯文字'}</span>
            <span>{sources[item.source_kind] || item.source_kind}{automatic ? ' · 自动采集' : ''}</span>
          </div>
          <h3>{item.title}</h3>
          <p>{automatic && <>排名 #{item.source_metrics.rank ?? '—'} · 热度 {item.source_metrics.hot_value?.toLocaleString() ?? '未提供'}<br /></>}
            {item.summary || '暂无摘要。进入工作流前请补充有权使用的原始素材。'}</p>
          <div className="card-bottom">
            <small>{dateFormat.format(new Date(item.collected_at || item.created_at))}</small>
            {automatic && item.source_url && <Button type="link" href={item.source_url} target="_blank" rel="noopener noreferrer">查看来源</Button>}
            <Button onClick={() => onCreate(item.id)} disabled={busy}>开始创作 ↗</Button>
          </div>
        </Card>
      })}</div>
      <div className="hotspot-pagination"><Pagination current={current} pageSize={pageSize} total={filtered.length}
        onChange={setPage} showSizeChanger={false} hideOnSinglePage responsive
        showTotal={total => `共 ${total} 条`} /></div>
    </> : <div className="hotspot-source-empty"><Empty description={source === 'manual'
      ? '暂无手动导入内容，点击「添加内容」提交参考素材。'
      : source === 'all' ? '暂无热点，请先采集来源或添加内容。'
        : `暂无${sourceLabel}热点，可在「采集来源」查看采集状态。`} /></div>}
  </section>
}

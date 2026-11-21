import { useEffect, useRef, useState } from 'react'
import './login.css'

export default function LoginScreen({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const hero = useRef<HTMLElement>(null)
  const usernameInput = useRef<HTMLInputElement>(null)
  const openButton = useRef<HTMLButtonElement>(null)
  const [loginOpen, setLoginOpen] = useState(false)
  const secondScreen = useRef<HTMLDivElement>(null)
  const showcase = useRef<HTMLElement>(null)
  const [revealed, setRevealed] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.documentElement.classList.add('entry-scrollbar')
    return () => document.documentElement.classList.remove('entry-scrollbar')
  }, [])

  useEffect(() => {
    const target = secondScreen.current
    if (!target) return
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setRevealed(true); return }
    const update = () => {
      const bounds = target.getBoundingClientRect()
      setRevealed(bounds.top < window.innerHeight * 0.85 && bounds.bottom > 0)
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => { window.removeEventListener('scroll', update); window.removeEventListener('resize', update) }
  }, [])

  useEffect(() => {
    const container = showcase.current
    if (!container || !('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const items = container.querySelectorAll<HTMLElement>('.showcase-image')
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      entry.target.classList.toggle('showcase-visible', entry.isIntersecting)
    }), { threshold: 0.1 })
    items.forEach(item => { item.classList.add('showcase-animated'); observer.observe(item) })
    return () => observer.disconnect()
  }, [])

  function openLogin() { setError(''); setLoginOpen(true); hero.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); window.setTimeout(() => usernameInput.current?.focus({ preventScroll: true }), 350) }
  function closeLogin() { if (busy) return; setLoginOpen(false); setPassword(''); setError(''); openButton.current?.focus({ preventScroll: true }) }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try { await onLogin(username, password) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="loom-entry">
    <EntryScrollbar />
    <header className="entry-nav">
      <a className="entry-logo" href="#">loom<span>CONTENT STUDIO</span></a>
    </header>
    <main>
      <section ref={hero} className={`entry-hero${loginOpen ? ' login-open' : ''}`} onKeyDown={e => { if (e.key === 'Escape' && loginOpen) closeLogin() }}>
        <div className="entry-particles" aria-hidden="true">{Array.from({ length: 38 }, (_, i) => <i key={i} style={{ left: `${(i * 37 + 11) % 100}%`, top: `${(i * 23 + 7) % 100}%`, animationDelay: `${-i * .7}s`, animationDuration: `${9 + i % 8}s`, '--twinkle-delay': `${-((i * 17) % 37)}s`, '--twinkle-duration': `${8 + (i * 7) % 11}s` } as React.CSSProperties}><span /></i>)}</div>
        <div className="entry-hero-layout"><div className="entry-hero-content">
          <p className="entry-eyebrow"><span/> LOOM · AI CONTENT WORKSPACE</p>
          <h1>让灵感在此汇聚<br/><span>让好内容开始流动</span></h1>
          <p className="entry-description">连接热点、产品与创作，让每一个想法走向成稿。<br/>与团队一起，在同一个工作空间里完成下一次创作。</p>
          <div className="entry-open-actions" inert={loginOpen} aria-hidden={loginOpen}><button ref={openButton} className="entry-primary" onClick={openLogin} aria-expanded={loginOpen} aria-controls="entry-login-panel">进入内容工作台</button></div>
        </div><div id="entry-login-panel" className="entry-inline-login" inert={!loginOpen} aria-hidden={!loginOpen}>
          <div className="entry-login-panel">
            <button className="entry-close" type="button" aria-label="关闭登录表单" disabled={busy} onClick={closeLogin}>×</button>
            <h2 id="entry-login-title">Welcome back</h2>
            <form onSubmit={submit}>
              <label htmlFor="entry-username">用户名</label><input ref={usernameInput} id="entry-username" autoComplete="username" required disabled={busy} value={username} onChange={e => setUsername(e.target.value)} placeholder="输入用户名"/>
              <label htmlFor="entry-password">密码</label><input id="entry-password" autoComplete="current-password" required disabled={busy} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="输入密码"/>
              {error && <div className="entry-error" role="alert">{error}</div>}
              <button className="entry-primary" disabled={busy}>{busy ? '正在登录…' : '登录工作台'}</button>
            </form>
          </div>
        </div></div>
      </section>
      <section ref={showcase} className="entry-showcase" aria-labelledby="showcase-title">
        <div className="showcase-heading"><p className="entry-eyebrow">CREATIVE SHOWCASE</p><h2 id="showcase-title">灵感，拥有无限可能</h2><p>每一个想法，都值得被看见。</p><small>图片展示示例</small></div>
        <div className="showcase-grid">{Array.from({ length: 4 }, (_, column) => <div className="showcase-column" key={column}>{Array.from({ length: 3 }, (_, row) => { const number = column * 3 + row + 1; return <div className="showcase-image" key={number} style={{ '--showcase-delay': `${100 + (number - 1) * 50}ms` } as React.CSSProperties}><img src={`/showcase/${number}.jpg`} alt={`创意图片展示示例 ${number}`} loading="lazy" /><span className="showcase-caption">创意展示 · 示例</span></div> })}</div>)}</div>
      </section>
      <div ref={secondScreen} className={`entry-second-screen${revealed ? ' is-revealed' : ''}`} id="entry-features">
      <section className="entry-features" aria-labelledby="entry-features-title">
        <h2 id="entry-features-title">创作的每一步，都有迹可循</h2>
        <p className="entry-features-intro">从发现灵感到完成创作，在一个空间里<br/>连接内容、产品与团队。</p>
        <div className="entry-feature-grid">{[
          ['discover', '汇聚内容灵感', '收集值得关注的图文与视频，为下一次创作找到切入点。'],
          ['flow', '串联创作流程', '从素材确认到内容定稿，让每个环节清晰可见。'],
          ['library', '沉淀团队资料', '集中管理产品信息，让创作建立在可靠的资料之上。'],
        ].map(([icon, title, description]) => <article key={title}><span className="entry-feature-icon" aria-hidden="true"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">{icon === 'discover' ? <><circle cx="12" cy="14" r="4"/><circle cx="36" cy="14" r="4"/><path d="M12 18c0 10 5 17 12 17s12-7 12-17M19 23l4 4 7-7"/></> : icon === 'flow' ? <path d="M27 4 9 27h13l-2 17 19-24H26z"/> : <><rect x="8" y="18" width="32" height="23" rx="3"/><path d="M15 18v-6a9 9 0 0 1 18 0v6"/><circle cx="24" cy="29" r="2"/></>}</svg></span><h3>{title}</h3><p>{description}</p></article>)}</div>
      </section>
      <section className="entry-cta" aria-labelledby="entry-cta-title">
        <h2 id="entry-cta-title">准备好开启你的创作了吗？</h2>
        <p>让灵感、产品和团队在 Loom 汇聚，<br/>一起把每一个想法变成好内容。</p>
        <button className="entry-primary" onClick={openLogin}>开始创作</button>
      </section>
      <footer className="entry-footer"><strong>loom</strong><span>灵感有序，创作自由。</span><small>INTERNAL CONTENT WORKSPACE</small></footer>
      </div>
    </main>
  </div>
}

function EntryScrollbar() {
  const track = useRef<HTMLDivElement>(null)
  const dragOffset = useRef<number | null>(null)
  const [metrics, setMetrics] = useState({ top: 0, height: 0, max: 0, value: 0 })

  useEffect(() => {
    const update = () => {
      const viewport = window.innerHeight
      const total = document.documentElement.scrollHeight
      const max = Math.max(0, total - viewport)
      const height = Math.min(viewport, Math.max(42, viewport * viewport / total))
      setMetrics({ top: max ? Math.min(max, Math.max(0, window.scrollY)) / max * (viewport - height) : 0, height, max, value: Math.min(max, Math.max(0, window.scrollY)) })
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    const observer = new ResizeObserver(update)
    observer.observe(document.body)
    return () => { window.removeEventListener('scroll', update); window.removeEventListener('resize', update); observer.disconnect() }
  }, [])

  function move(clientY: number, offset: number) {
    const rect = track.current?.getBoundingClientRect()
    if (!rect) return
    const available = rect.height - metrics.height
    if (available > 0) window.scrollTo({ top: Math.max(0, Math.min(1, (clientY - rect.top - offset) / available)) * metrics.max, behavior: 'instant' })
  }
  function keyScroll(event: React.KeyboardEvent) {
    const values: Record<string, number> = { ArrowDown: 40, ArrowUp: -40, PageDown: window.innerHeight, PageUp: -window.innerHeight, Home: -metrics.max, End: metrics.max }
    if (event.key in values) { event.preventDefault(); window.scrollBy({ top: values[event.key], behavior: 'instant' }) }
  }
  if (!metrics.max) return null
  return <div ref={track} className="entry-custom-scroll" role="scrollbar" aria-label="页面滚动" aria-orientation="vertical" aria-valuemin={0} aria-valuemax={Math.round(metrics.max)} aria-valuenow={Math.round(metrics.value)} tabIndex={0} onKeyDown={keyScroll} onPointerDown={event => { if (event.button !== 0) return; const thumb = event.currentTarget.querySelector('.entry-custom-thumb')?.getBoundingClientRect(); dragOffset.current = event.target === event.currentTarget || !thumb ? metrics.height / 2 : event.clientY - thumb.top; event.currentTarget.setPointerCapture(event.pointerId); move(event.clientY, dragOffset.current) }} onPointerMove={event => { if (dragOffset.current !== null) move(event.clientY, dragOffset.current) }} onPointerUp={() => { dragOffset.current = null }} onPointerCancel={() => { dragOffset.current = null }} onLostPointerCapture={() => { dragOffset.current = null }}><div className="entry-custom-thumb" style={{ height: metrics.height, transform: `translateY(${metrics.top}px)` }}/></div>
}

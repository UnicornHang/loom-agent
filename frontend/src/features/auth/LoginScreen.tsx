import { useRef, useState } from 'react'
import './login.css'

export default function LoginScreen({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function openLogin() { setError(''); dialog.current?.showModal() }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try { await onLogin(username, password) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="loom-entry">
    <header className="entry-nav">
      <a className="entry-logo" href="#">loom<span>CONTENT STUDIO</span></a>
    </header>
    <main>
      <section className="entry-hero">
        <div className="entry-particles" aria-hidden="true">{Array.from({ length: 38 }, (_, i) => <i key={i} style={{ left: `${(i * 37 + 11) % 100}%`, top: `${(i * 23 + 7) % 100}%`, animationDelay: `${-i * .7}s`, animationDuration: `${9 + i % 8}s` }}/>)}</div>
        <div className="entry-hero-content">
          <p className="entry-eyebrow"><span/> LOOM · AI CONTENT WORKSPACE</p>
          <h1>让灵感在此汇聚<br/><span>让好内容开始流动</span></h1>
          <p className="entry-description">连接热点、产品与创作，让每一个想法走向成稿。<br/>与团队一起，在同一个工作空间里完成下一次创作。</p>
          <button className="entry-primary" onClick={openLogin}>进入内容工作台 <span aria-hidden="true">→</span></button>
          <p className="entry-access">使用团队账号登录，开启你的创作流程</p>
        </div>
        <a className="entry-scroll" href="#entry-features">探索工作空间 <span aria-hidden="true">↓</span></a>
      </section>
      <section className="entry-features" id="entry-features" aria-labelledby="entry-features-title">
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
    </main>
    <footer className="entry-footer"><strong>loom</strong><span>灵感有序，创作自由。</span><small>INTERNAL CONTENT WORKSPACE</small></footer>
    <dialog className="entry-dialog" ref={dialog} aria-labelledby="entry-login-title" onCancel={e => { if (busy) e.preventDefault() }} onClick={e => { if (e.target === e.currentTarget && !busy) dialog.current?.close() }} onClose={() => { setPassword(''); setError('') }}>
      <div className="entry-login-panel">
        <button className="entry-close" type="button" aria-label="关闭登录表单" disabled={busy} onClick={() => dialog.current?.close()}>×</button>
        <p className="entry-eyebrow">WELCOME BACK</p><h2 id="entry-login-title">登录内容工作台</h2><p className="entry-login-intro">使用管理员为你创建的团队账号。</p>
        <form onSubmit={submit}>
          <label htmlFor="entry-username">用户名</label><input id="entry-username" autoFocus autoComplete="username" required disabled={busy} value={username} onChange={e => setUsername(e.target.value)} placeholder="输入用户名"/>
          <label htmlFor="entry-password">密码</label><input id="entry-password" autoComplete="current-password" required disabled={busy} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="输入密码"/>
          {error && <div className="entry-error" role="alert">{error}</div>}
          <button className="entry-primary" disabled={busy}>{busy ? '正在登录…' : '登录工作台'}<span aria-hidden="true">→</span></button>
        </form>
        <p className="entry-login-help">还没有账号？请联系团队管理员。</p>
      </div>
    </dialog>
  </div>
}

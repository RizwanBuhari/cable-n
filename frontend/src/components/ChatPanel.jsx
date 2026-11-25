// Cable-N Assistant - Track-N's chat panel design. Optional: when the site
// has no AI configured, the panel explains that instead of failing. Context
// is only sent when the visitor ticks "Share the current calculation"; the
// server then recomputes it with the engine (results are never taken from the
// browser). The assistant can't change anything.
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Icon } from './icons'

const CalcCtx = createContext({ current: null, setCurrent: () => {} })
export function CalcContextProvider({ children }) {
  const [current, setCurrent] = useState(null)
  return <CalcCtx.Provider value={{ current, setCurrent }}>{children}</CalcCtx.Provider>
}
/** Calculators call this so the assistant can offer to share their inputs. */
export function useShareableCalc(value) {
  const { setCurrent } = useContext(CalcCtx)
  const key = value ? JSON.stringify(value) : ''
  useEffect(() => {
    setCurrent(value)
    return () => setCurrent(null)
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
}

const SUGGESTIONS = [
  'What does the grouping factor Cg mean?',
  'Why would a cable pass ampacity but fail voltage drop?',
  'What is the difference between T1, T2, T3 and T4?',
]

export default function ChatPanel() {
  const { current } = useContext(CalcCtx)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [share, setShare] = useState(false)
  const bodyRef = useRef(null)

  useEffect(() => {
    if (open && !status) api('/assistant/status').then(setStatus).catch(() => setStatus({ configured: false, message: 'The assistant is unavailable.' }))
  }, [open, status])
  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight }, [messages, busy])
  useEffect(() => {
    if (!open) return undefined
    const k = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open])
  useEffect(() => { if (!current) setShare(false) }, [current])

  async function send(text) {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setInput('')
    const history = messages.filter((m) => !m.error).map((m) => ({ role: m.role, text: m.text }))
    setMessages((m) => [...m, { role: 'user', text: q, shared: share && current ? current.label : null }])
    setBusy(true)
    try {
      const r = await api('/assistant/chat', { method: 'POST', body: { message: q, history, share: share && current ? { mode: current.mode, inputs: current.inputs } : null } })
      setMessages((m) => [...m, { role: 'assistant', text: r.answer }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', error: true, text: e.message }])
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button className="chat-fab" onClick={() => setOpen(true)} aria-label="Ask the Cable-N Assistant">
        {Icon.chat}
        <span>Ask</span>
      </button>
    )
  }
  const ready = status?.configured
  return (
    <aside className="chat-panel" role="dialog" aria-label="Cable-N Assistant">
      <header className="chat-head">
        <div className="chat-head-id">
          <span className="chat-avatar" aria-hidden="true">{Icon.chat}</span>
          <div>
            <strong>Cable-N Assistant</strong>
            <span className="chat-sub">
              {ready && <span className="chat-status-dot" aria-hidden="true" />}
              {ready ? 'Explains results · cannot change or approve them' : status ? 'Not enabled on this site' : 'Checking…'}
            </span>
          </div>
        </div>
        <button className="chat-close" onClick={() => setOpen(false)} aria-label="Close">×</button>
      </header>
      {status && !ready ? (
        <div className="chat-off">
          <p>{status.message}</p>
          <p>You can still use every calculator, report and export. The Engineering Resources page explains the methods and symbols.</p>
        </div>
      ) : (
        <>
          <div className="chat-body" ref={bodyRef}>
            {messages.length === 0 && (
              <div className="chat-empty">
                <p>Ask about cable sizing terms, correction factors, why a check failed, or how to use a calculator. Answers are AI-generated explanations — the numbers always come from the Cable-N engine.</p>
                <div className="chat-suggestions">
                  {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)} disabled={busy}>{s}</button>)}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg chat-${m.role}${m.error ? ' chat-error' : ''}`}>
                {m.shared && <div className="small" style={{ opacity: 0.8, marginBottom: 4 }}>Shared: {m.shared}</div>}
                <div className="chat-text">{m.text}</div>
              </div>
            ))}
            {busy && <div className="chat-msg chat-assistant chat-typing"><span /><span /><span /></div>}
          </div>
          {current && (
            <label className="chat-share">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
              Share the current calculation ({current.label}) with the AI provider
            </label>
          )}
          <div className="chat-input">
            <textarea rows={1} value={input} placeholder="Ask about a result or a term…" maxLength={2000}
              onChange={(e) => setInput(e.target.value)} disabled={busy}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
            <button className="chat-send" onClick={() => send()} disabled={busy || !input.trim()} aria-label="Send">{Icon.send}</button>
          </div>
        </>
      )}
    </aside>
  )
}

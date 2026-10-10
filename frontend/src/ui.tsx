import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

/* ---------- уведомления ---------- */
type Toast = { id: number; text: string; error?: boolean }
const ToastCtx = createContext<(text: string, error?: boolean) => void>(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const push = useCallback((text: string, error = false) => {
    const id = Date.now() + Math.random()
    setItems(xs => [...xs, { id, text, error }])
    setTimeout(() => setItems(xs => xs.filter(x => x.id !== id)), error ? 6000 : 3000)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map(t => <div key={t.id} className={`toast${t.error ? ' error' : ''}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  )
}

/** Обёртка для действий: ошибку API показывает уведомлением. */
export function useAction() {
  const toast = useToast()
  return useCallback(async <T,>(fn: () => Promise<T>, ok?: string): Promise<T | undefined> => {
    try {
      const r = await fn()
      if (ok) toast(ok)
      return r
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), true)
      return undefined
    }
  }, [toast])
}

/* ---------- данные ---------- */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    load().then(d => { if (alive) { setData(d); setError(null) } })
      .catch(e => { if (alive) setError(e instanceof Error ? e.message : String(e)) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { data, error, reload: () => setTick(t => t + 1), setData }
}

/* ---------- готовность ---------- */
export function Progress({ value, big, onChange }: { value: number; big?: boolean; onChange?: (v: number) => void }) {
  const [local, setLocal] = useState(value)
  useEffect(() => setLocal(value), [value])
  return (
    <div className={`progress${big ? ' big' : ''}`}>
      <div className="bar">
        <i style={{ width: `${local}%` }} />
        {onChange && (
          <input type="range" min={0} max={100} step={5} value={local} aria-label="Готовность, %"
            onChange={e => setLocal(Number(e.target.value))}
            onPointerUp={() => local !== value && onChange(local)}
            onKeyUp={() => local !== value && onChange(local)} />
        )}
      </div>
      <span className="pct">{local}%</span>
    </div>
  )
}

/* ---------- поле, сохраняемое при уходе фокуса ---------- */
export function EditableText({ value, onSave, multiline, placeholder, className, ariaLabel }: {
  value: string; onSave: (v: string) => void; multiline?: boolean; placeholder?: string; className?: string; ariaLabel?: string
}) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  const commit = () => { if (v.trim() !== value.trim()) onSave(v.trim()) }
  const common = {
    value: v, placeholder, 'aria-label': ariaLabel,
    onChange: (e: { target: { value: string } }) => setV(e.target.value),
    onBlur: commit,
  }
  if (multiline) {
    return <textarea {...common} className={`textarea inline-edit ${className ?? ''}`} rows={Math.max(2, v.split('\n').length + 1)} />
  }
  return <input {...common} className={className ?? 'input inline-edit'}
    onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') { setV(value); setTimeout(() => (e.target as HTMLInputElement).blur()) } }} />
}

/* ---------- лист (sheet) в стиле iOS ---------- */
function useModal(onClose: () => void, ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    ref.current?.querySelector<HTMLElement>('[data-autofocus], input, textarea, select')?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('keydown', onKey); prev?.focus() }
  }, [onClose, ref])
}

export function Sheet({ title, children, onClose, done, doneLabel = 'Готово', cancelLabel = 'Отмена', wide }: {
  title: string; children: ReactNode; onClose: () => void; done?: () => void; doneLabel?: string; cancelLabel?: string; wide?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useModal(onClose, ref)
  return (
    <div className="scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className={`sheet${wide ? ' wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="grabber" />
        <div className="sheet-bar">
          <button className="btn plain" style={{ justifySelf: 'start' }} onClick={onClose}>{done ? cancelLabel : 'Закрыть'}</button>
          <h2>{title}</h2>
          {done ? <button className="btn plain right" style={{ fontWeight: 600 }} onClick={done}>{doneLabel}</button> : <span />}
        </div>
        <div className="sheet-body">{children}</div>
      </div>
    </div>
  )
}

/** Предупреждение для необратимых действий. */
export function Alert({ title, text, confirm, onConfirm, onClose }: {
  title: string; text: string; confirm: string; onConfirm: () => void; onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useModal(onClose, ref)
  return (
    <div className="scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="alert" role="alertdialog" aria-modal="true" aria-label={title} ref={ref}>
        <h2>{title}</h2>
        <p>{text}</p>
        <div className="buttons">
          <button onClick={onClose} data-autofocus>Отмена</button>
          <button className="destructive" onClick={onConfirm}>{confirm}</button>
        </div>
      </div>
    </div>
  )
}

export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  )
}

export function Section({ title, action, foot, children }: { title?: string; action?: ReactNode; foot?: string; children: ReactNode }) {
  return (
    <section className="section">
      {title && <h3 className="section-title">{title}{action && <span className="act">{action}</span>}</h3>}
      <div className="group">{children}</div>
      {foot && <p className="section-foot">{foot}</p>}
    </section>
  )
}

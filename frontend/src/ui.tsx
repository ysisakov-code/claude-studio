import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Stage } from './types'
import { STAGE_LABEL } from './util'

/* ---------- уведомления ---------- */
type Toast = { id: number; text: string; error?: boolean }
const ToastCtx = createContext<(text: string, error?: boolean) => void>(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const push = useCallback((text: string, error = false) => {
    const id = Date.now() + Math.random()
    setItems(xs => [...xs, { id, text, error }])
    setTimeout(() => setItems(xs => xs.filter(x => x.id !== id)), error ? 6000 : 3200)
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

/** Обёртка для действий: показывает ошибку API уведомлением. */
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

/* ---------- линейка прогресса ---------- */
export function Ruler({ value, big, onChange }: { value: number; big?: boolean; onChange?: (v: number) => void }) {
  const [local, setLocal] = useState(value)
  useEffect(() => setLocal(value), [value])
  return (
    <div className={`ruler${big ? ' big' : ''}`}>
      <div className="track">
        <div className="fill" style={{ width: `${local}%` }} />
        {onChange && (
          <input type="range" min={0} max={100} step={5} value={local} aria-label="Готовность, %"
            onChange={e => setLocal(Number(e.target.value))}
            onPointerUp={() => local !== value && onChange(local)}
            onKeyUp={() => local !== value && onChange(local)} />
        )}
      </div>
      <span className="val">{local}%</span>
    </div>
  )
}

export function StageDot({ stage }: { stage: Stage }) {
  return <span className={`tab-${stage}`} style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3 }} aria-label={STAGE_LABEL[stage]} />
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
    return <textarea {...common} className={`textarea inline-edit ${className ?? ''}`} rows={Math.max(3, v.split('\n').length + 1)} />
  }
  return <input {...common} className={`input inline-edit ${className ?? ''}`}
    onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') { setV(value); setTimeout(() => (e.target as HTMLInputElement).blur()) } }} />
}

/* ---------- диалог ---------- */
export function Dialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    ref.current?.querySelector<HTMLElement>('input, textarea, select, button')?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('keydown', onKey); prev?.focus() }
  }, [onClose])
  return (
    <div className="scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <h2>{title}</h2>
        {children}
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

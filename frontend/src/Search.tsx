import { MessagesSquare, Search as SearchIcon } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from './api'
import { Cover } from './Cover'
import type { ProjectCard, SessionItem } from './types'
import { STAGE_LABEL, relDate } from './util'

type Result = { projects: ProjectCard[]; sessions: SessionItem[] }
type Hit = { key: string; title: string; sub: string; lead: ReactNode; go: () => void }

export function SearchPalette({ onClose, openProject, openSessions }: {
  onClose: () => void; openProject: (id: number) => void; openSessions: () => void
}) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState<Result | null>(null)
  const [sel, setSel] = useState(0)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => { input.current?.focus() }, [])
  useEffect(() => {
    if (!q.trim()) { setRes(null); return }
    const t = setTimeout(() => {
      api.get<Result>(`/api/search?q=${encodeURIComponent(q.trim())}`).then(r => { setRes(r); setSel(0) }).catch(() => setRes(null))
    }, 120)
    return () => clearTimeout(t)
  }, [q])

  const hits: Hit[] = [
    ...(res?.projects ?? []).map(p => ({
      key: `p${p.id}`, title: p.name, sub: p.parent_name ?? STAGE_LABEL[p.stage],
      lead: <Cover p={p} showIcon={false} />, go: () => openProject(p.id),
    })),
    ...(res?.sessions ?? []).slice(0, 12).map(s => ({
      key: `s${s.id}`, title: s.display_title, sub: relDate(s.ended_at),
      lead: <span className="icon-tile" style={{ background: 'var(--purple)', width: 32, height: 32 }}><MessagesSquare size={16} /></span>,
      go: () => (s.project_id ? openProject(s.project_id) : openSessions()),
    })),
  ]
  const choose = (h?: Hit) => { if (h) { h.go(); onClose() } }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(s + 1, hits.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(s - 1, 0)) }
    else if (e.key === 'Enter') choose(hits[sel])
  }
  const nProjects = res?.projects.length ?? 0

  return (
    <div className="scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Поиск">
        <div className="search-input">
          <SearchIcon size={19} />
          <input ref={input} placeholder="Проект, тег или что спрашивали у Claude" value={q}
            onChange={e => setQ(e.target.value)} onKeyDown={onKey} aria-label="Поиск" />
          <button className="btn plain" onClick={onClose}>Отмена</button>
        </div>
        <div className="results" role="listbox">
          {!q.trim() && <div className="empty">Ищет по названиям проектов, тегам, заметкам и запросам в сессиях.</div>}
          {res && hits.length === 0 && <div className="empty">Ничего не нашлось по «{q}».</div>}
          {hits.map((h, i) => (
            <div key={h.key}>
              {i === 0 && nProjects > 0 && <div className="group-label">Проекты</div>}
              {i === nProjects && <div className="group-label">Сессии</div>}
              <button className="hit" role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onClick={() => choose(h)}>
                {h.lead}<span>{h.title}</span><span className="s">{h.sub}</span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

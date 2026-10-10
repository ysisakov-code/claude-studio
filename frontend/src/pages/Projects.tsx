import { DndContext, DragOverlay, PointerSensor, KeyboardSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { Columns3, LayoutGrid, MessageSquare, PenLine, Plus } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import type { ProjectCard, ProjectDetail, Stage } from '../types'
import { Dialog, EmptyState, Ruler, useAction, useLoad } from '../ui'
import { STAGES, STAGE_LABEL, nDays, nRecs, relDate } from '../util'

type View = 'grid' | 'board'
const VIEW_KEY = 'studio.view'

export function ProjectsPage({ open, version }: { open: (id: number) => void; version: number }) {
  const { data, reload, setData } = useLoad(() => api.get<ProjectCard[]>('/api/projects'), [version])
  const [view, setView] = useState<View>(() => (localStorage.getItem(VIEW_KEY) as View) || 'grid')
  const [creating, setCreating] = useState(false)
  const act = useAction()

  const switchView = (v: View) => { setView(v); try { localStorage.setItem(VIEW_KEY, v) } catch { /* нет хранилища */ } }

  const moveStage = async (id: number, stage: Stage) => {
    const prev = data
    setData(xs => xs?.map(p => p.id === id ? { ...p, stage } : p) ?? null)
    const ok = await act(() => api.patch(`/api/projects/${id}`, { stage }), `Стадия: ${STAGE_LABEL[stage]}`)
    if (ok === undefined) setData(prev)
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="page-title">Проекты</h1>
        <span className="spacer" />
        <div className="seg" role="group" aria-label="Вид">
          <button aria-pressed={view === 'grid'} onClick={() => switchView('grid')}><LayoutGrid size={15} />Карточки</button>
          <button aria-pressed={view === 'board'} onClick={() => switchView('board')}><Columns3 size={15} />По стадиям</button>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}><Plus size={16} />Новый проект</button>
      </div>

      {data === null ? null : data.length === 0 ? (
        <EmptyState title="Заведите первый проект"
          text="Проект — это то, над чем вы работаете с Claude. Его можно создать вручную или из папки в разделе «Разобрать»."
          action={<button className="btn primary" onClick={() => setCreating(true)}><Plus size={16} />Новый проект</button>} />
      ) : view === 'grid' ? (
        <div className="grid">
          {data.map(p => <Card key={p.id} p={p} onOpen={() => open(p.id)} />)}
          <button className="pcard new" onClick={() => setCreating(true)}><Plus size={20} />Новый проект</button>
        </div>
      ) : (
        <Board projects={data} onOpen={open} onMove={moveStage} />
      )}

      {creating && <NewProjectDialog onClose={() => setCreating(false)} onCreated={p => { setCreating(false); reload(); open(p.id) }} />}
    </div>
  )
}

function Card({ p, onOpen }: { p: ProjectCard; onOpen: () => void }) {
  return (
    <button className={`pcard${p.is_stale ? ' stale' : ''}`} onClick={onOpen}>
      <span className={`tab tab-${p.stage}`}>{STAGE_LABEL[p.stage]}</span>
      <h3>{p.name}</h3>
      {p.next_step ? <p className="next">{p.next_step}</p> : p.description ? <p className="desc">{p.description}</p> : null}
      <Ruler value={p.progress} />
      <div className="foot">
        {p.is_stale && p.days_inactive !== null
          ? <span className="stale-note">{nDays(p.days_inactive)} без работы</span>
          : <span>{relDate(p.last_activity)}</span>}
        {p.open_recommendations > 0 && <span className="recs" title="Открытые доработки"><PenLine size={13} />{p.open_recommendations}</span>}
        <span className="push" title="Сессии Claude Code"><MessageSquare size={13} style={{ verticalAlign: -2 }} /> {p.session_count}</span>
      </div>
    </button>
  )
}

/* ---------- доска ---------- */
function Board({ projects, onOpen, onMove }: { projects: ProjectCard[]; onOpen: (id: number) => void; onMove: (id: number, s: Stage) => void }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor))
  const [active, setActive] = useState<ProjectCard | null>(null)
  const onEnd = (e: DragEndEvent) => {
    setActive(null)
    const stage = e.over?.id as Stage | undefined
    const p = projects.find(x => x.id === e.active.id)
    if (p && stage && stage !== p.stage) onMove(p.id, stage)
  }
  return (
    <DndContext sensors={sensors} onDragStart={e => setActive(projects.find(p => p.id === e.active.id) ?? null)}
      onDragEnd={onEnd} onDragCancel={() => setActive(null)}>
      <div className="board">
        {STAGES.map(s => (
          <Column key={s.id} stage={s.id} label={s.label} hint={s.hint}
            items={projects.filter(p => p.stage === s.id)} onOpen={onOpen} />
        ))}
      </div>
      <DragOverlay dropAnimation={null}>{active && <Mini p={active} overlay />}</DragOverlay>
    </DndContext>
  )
}

function Column({ stage, label, hint, items, onOpen }: { stage: Stage; label: string; hint: string; items: ProjectCard[]; onOpen: (id: number) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage })
  return (
    <section ref={setNodeRef} className={`column${isOver ? ' over' : ''}`} aria-label={label}>
      <div className="column-head" title={hint}><span className={`bar tab-${stage}`} />{label}<span className="n">{items.length}</span></div>
      <div className="column-body">
        {items.map(p => <DraggableMini key={p.id} p={p} onOpen={() => onOpen(p.id)} />)}
      </div>
    </section>
  )
}

function DraggableMini({ p, onOpen }: { p: ProjectCard; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: p.id })
  return (
    <div ref={setNodeRef} {...attributes} {...listeners} onClick={onOpen}
      onKeyDown={e => { listeners?.onKeyDown?.(e); if (e.key === 'Enter') onOpen() }}>
      <Mini p={p} dragging={isDragging} />
    </div>
  )
}

function Mini({ p, dragging, overlay }: { p: ProjectCard; dragging?: boolean; overlay?: boolean }) {
  return (
    <div className={`mini${dragging ? ' dragging' : ''}${overlay ? ' overlay' : ''}${p.is_stale ? ' stale' : ''}`}>
      <b>{p.name}</b>
      <Ruler value={p.progress} />
      <div className="meta">
        <span>{p.is_stale && p.days_inactive !== null ? <span className="stale-note">{nDays(p.days_inactive)} без работы</span> : relDate(p.last_activity)}</span>
        {p.open_recommendations > 0 && <span className="prio-high" title={nRecs(p.open_recommendations)}>✎ {p.open_recommendations}</span>}
      </div>
    </div>
  )
}

/* ---------- новый проект ---------- */
export function NewProjectDialog({ onClose, onCreated, initial }: {
  onClose: () => void; onCreated: (p: ProjectDetail) => void; initial?: { name?: string; path?: string; description?: string }
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [path, setPath] = useState(initial?.path ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [stage, setStage] = useState<Stage>('idea')
  const [err, setErr] = useState('')
  const act = useAction()
  const submit = async () => {
    if (!name.trim()) { setErr('Введите название'); return }
    const p = await act(() => api.post<ProjectDetail>('/api/projects', {
      name: name.trim(), description, stage, paths: path.trim() ? [path.trim()] : [],
    }), 'Проект создан')
    if (p) onCreated(p)
  }
  return (
    <Dialog title="Новый проект" onClose={onClose}>
      <label className="field"><span>Название</span>
        <input className="input" value={name} onChange={e => { setName(e.target.value); setErr('') }} placeholder="Исторический атлас ЕГЭ"
          onKeyDown={e => e.key === 'Enter' && submit()} />
        {err && <span style={{ color: 'var(--pen)', fontSize: 13 }}>{err}</span>}
      </label>
      <label className="field"><span>Папка проекта, если есть</span>
        <input className="input" value={path} onChange={e => setPath(e.target.value)} placeholder="C:\Users\…\Documents\atlas" />
      </label>
      <label className="field"><span>Коротко о проекте</span>
        <textarea className="textarea" value={description} onChange={e => setDescription(e.target.value)} placeholder="~70 карт для подготовки к ЕГЭ" />
      </label>
      <label className="field"><span>Стадия</span>
        <select className="select" value={stage} onChange={e => setStage(e.target.value as Stage)}>
          {STAGES.map(s => <option key={s.id} value={s.id}>{s.label} — {s.hint.toLowerCase()}</option>)}
        </select>
      </label>
      <div className="actions">
        <button className="btn ghost" onClick={onClose}>Отмена</button>
        <button className="btn primary" onClick={submit}>Создать проект</button>
      </div>
    </Dialog>
  )
}

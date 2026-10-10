import { DndContext, DragOverlay, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { Columns3, LayoutGrid, Plus, Wrench } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import { api } from '../api'
import { Cover } from '../Cover'
import { projectTheme } from '../theme'
import type { ProjectCard, ProjectDetail, Stage } from '../types'
import { EmptyState, Progress, Sheet, useAction, useLoad } from '../ui'
import { STAGES, STAGE_LABEL, nDays, relDate } from '../util'

type View = 'grid' | 'board'
const VIEW_KEY = 'studio.view'
export const STAGE_COLOR: Record<Stage, string> = {
  idea: 'var(--purple)', design: 'var(--teal)', build: 'var(--orange)', live: 'var(--green)', paused: 'var(--gray)', archived: 'var(--gray)',
}

export function ProjectsPage({ open, version }: { open: (id: number) => void; version: number }) {
  const { data, reload, setData } = useLoad(() => api.get<ProjectCard[]>('/api/projects'), [version])
  const [view, setView] = useState<View>(() => { try { return (localStorage.getItem(VIEW_KEY) as View) || 'grid' } catch { return 'grid' } })
  const [creating, setCreating] = useState(false)
  const act = useAction()

  const switchView = (v: View) => { setView(v); try { localStorage.setItem(VIEW_KEY, v) } catch { /* нет хранилища */ } }
  const moveStage = async (id: number, stage: Stage) => {
    const prev = data
    setData(xs => xs?.map(p => p.id === id ? { ...p, stage } : p) ?? null)
    const ok = await act(() => api.patch(`/api/projects/${id}`, { stage }), `Стадия: ${STAGE_LABEL[stage]}`)
    if (ok === undefined) setData(prev)
  }
  const all = data ?? []
  const top = all.filter(p => !p.parent_id)

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="large-title">Проекты</h1>
        <span className="spacer" />
        <div className="segmented" role="group" aria-label="Вид">
          <button aria-pressed={view === 'grid'} onClick={() => switchView('grid')}><LayoutGrid size={14} />Обложки</button>
          <button aria-pressed={view === 'board'} onClick={() => switchView('board')}><Columns3 size={14} />По стадиям</button>
        </div>
        <button className="btn filled circle" aria-label="Новый проект" title="Новый проект" onClick={() => setCreating(true)}><Plus size={20} /></button>
      </div>

      {data === null ? null : all.length === 0 ? (
        <EmptyState title="Заведите первый проект"
          text="Проект — то, над чем вы работаете с Claude. Создайте его вручную или из папки в разделе «Разобрать»."
          action={<button className="btn filled" onClick={() => setCreating(true)}><Plus size={16} />Новый проект</button>} />
      ) : view === 'grid' ? (
        <div className="library">
          {top.map(p => <Tile key={p.id} p={p} all={all} onOpen={() => open(p.id)} />)}
          <button className="tile new" onClick={() => setCreating(true)}>
            <div className="cover"><span style={{ display: 'grid', justifyItems: 'center', gap: 6 }}><Plus size={28} />Новый проект</span></div>
          </button>
        </div>
      ) : (
        <Board projects={all} onOpen={open} onMove={moveStage} />
      )}

      {creating && <NewProjectSheet projects={top} onClose={() => setCreating(false)} onCreated={p => { setCreating(false); reload(); open(p.id) }} />}
    </div>
  )
}

export function Tile({ p, all, onOpen }: { p: ProjectCard; all: ProjectCard[]; onOpen: () => void }) {
  const t = projectTheme(p)
  const parts = all.filter(x => x.parent_id === p.id)
  return (
    <button className="tile" onClick={onOpen} style={{ '--tint': t.color } as CSSProperties}>
      <Cover p={p} parts={parts} dim={p.is_stale} />
      <div className="tile-body">
        <div className="tile-title">{p.name}</div>
        <div className="tile-sub">{p.next_step || p.description || STAGE_LABEL[p.stage]}</div>
        <Progress value={p.progress} />
        <div className="tile-meta">
          <span style={{ color: STAGE_COLOR[p.stage], fontWeight: 600 }}>{STAGE_LABEL[p.stage]}</span>
          <span className="dot-sep">·</span>
          {p.is_stale && p.days_inactive !== null
            ? <span className="warn">{nDays(p.days_inactive)} без работы</span>
            : <span>{relDate(p.last_activity)}</span>}
          {p.open_recommendations > 0 && <span className="recs" title="Открытые доработки" style={{ marginLeft: 'auto' }}><Wrench size={12} />{p.open_recommendations}</span>}
        </div>
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
      <div className="column-head" title={hint}><span className="dot" style={{ background: STAGE_COLOR[stage] }} />{label}<span className="n">{items.length}</span></div>
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
    <div className={`mini${dragging ? ' dragging' : ''}${overlay ? ' overlay' : ''}`} style={{ '--tint': projectTheme(p).color } as CSSProperties}>
      <Cover p={p} showIcon={false} dim={p.is_stale} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="t">{p.name}</div>
        <div className="s">{p.parent_name ? `${p.parent_name} · ` : ''}{p.progress}%{p.is_stale && p.days_inactive !== null ? <span className="warn"> · {nDays(p.days_inactive)}</span> : ''}</div>
      </div>
    </div>
  )
}

/* ---------- новый проект ---------- */
export function NewProjectSheet({ onClose, onCreated, projects, initial }: {
  onClose: () => void; onCreated: (p: ProjectDetail) => void; projects: ProjectCard[]
  initial?: { name?: string; path?: string; description?: string; parent_id?: number }
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [path, setPath] = useState(initial?.path ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [stage, setStage] = useState<Stage>('idea')
  const [parent, setParent] = useState(initial?.parent_id ? String(initial.parent_id) : '')
  const [err, setErr] = useState('')
  const act = useAction()
  const submit = async () => {
    if (!name.trim()) { setErr('Введите название'); return }
    const p = await act(() => api.post<ProjectDetail>('/api/projects', {
      name: name.trim(), description, stage, paths: path.trim() ? [path.trim()] : [],
      parent_id: parent ? Number(parent) : null,
    }), 'Проект создан')
    if (p) onCreated(p)
  }
  return (
    <Sheet title="Новый проект" onClose={onClose} done={submit} doneLabel="Создать">
      <label className="field"><span>Название</span>
        <input className="input" value={name} onChange={e => { setName(e.target.value); setErr('') }} placeholder="Исторический атлас ЕГЭ"
          onKeyDown={e => e.key === 'Enter' && submit()} />
        {err && <span className="error-text">{err}</span>}
      </label>
      <label className="field"><span>Коротко о проекте</span>
        <textarea className="textarea" value={description} onChange={e => setDescription(e.target.value)} placeholder="~70 карт для подготовки к ЕГЭ" />
      </label>
      <label className="field"><span>Папка проекта, если есть</span>
        <input className="input" value={path} onChange={e => setPath(e.target.value)} placeholder="C:\Users\…\Documents\atlas" />
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="field"><span>Стадия</span>
          <select className="select" value={stage} onChange={e => setStage(e.target.value as Stage)}>
            {STAGES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
        <label className="field"><span>Входит в проект</span>
          <select className="select" value={parent} onChange={e => setParent(e.target.value)}>
            <option value="">Самостоятельный</option>
            {projects.filter(p => !p.parent_id).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </div>
    </Sheet>
  )
}

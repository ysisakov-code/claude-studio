import { ArrowLeft, ExternalLink, FileText, FolderOpen, GitBranch, Lightbulb, Pin, PinOff, Play, Plus, RotateCcw, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import type { ActivityEntry, Agent, Link, Priority, ProjectCard, ProjectDetail, RecStatus, Recommendation, SessionItem, Stage, StageEntry } from '../types'
import { Dialog, EditableText, EmptyState, Ruler, useAction, useLoad, useToast } from '../ui'
import { PRIORITY_LABEL, REC_STATUS_LABEL, STAGES, STAGE_LABEL, duration, fullDate, nPrompts, relDate } from '../util'

type Tab = 'overview' | 'sessions' | 'agents' | 'recs' | 'journal'

export function ProjectPage({ id, back, onChanged }: { id: number; back: () => void; onChanged: () => void }) {
  const { data: p, setData, error } = useLoad(() => api.get<ProjectDetail>(`/api/projects/${id}`), [id])
  const [tab, setTab] = useState<Tab>('overview')
  const act = useAction()
  const toast = useToast()

  if (error) return <div className="page"><button className="btn ghost back" onClick={back}><ArrowLeft size={16} />Все проекты</button><EmptyState title="Проект не открылся" text={error} /></div>
  if (!p) return <div className="page" />

  const save = async (patch: Record<string, unknown>, ok?: string) => {
    const r = await act(() => api.patch<ProjectDetail>(`/api/projects/${id}`, patch), ok)
    if (r) { setData(r); onChanged() }
  }
  const primary = p.paths.find(x => x.is_primary) ?? p.paths[0]
  const openPath = (path: string) => act(() => api.post('/api/open', { path }))
  const notYet = () => toast('Запуск Claude появится на следующем этапе: кнопка откроет терминал с Claude в папке проекта')

  return (
    <div className="page">
      <button className="btn ghost back" onClick={back}><ArrowLeft size={16} />Все проекты</button>
      <div className="proj-head">
        <div>
          <EditableText value={p.name} onSave={v => v && save({ name: v })} className="proj-title" ariaLabel="Название проекта" />
          <div className="proj-meta">
            <select className={`select stage-select tab-${p.stage}`} value={p.stage} aria-label="Стадия"
              onChange={e => save({ stage: e.target.value as Stage }, `Стадия: ${STAGE_LABEL[e.target.value as Stage]}`)}>
              {[...STAGES, { id: 'archived' as Stage, label: 'В архиве' }].map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <div style={{ width: 260 }}><Ruler big value={p.progress} onChange={v => save({ progress: v })} /></div>
            <select className="select" style={{ width: 'auto' }} value={p.priority} aria-label="Приоритет"
              onChange={e => save({ priority: e.target.value as Priority })}>
              {(['high', 'normal', 'low'] as Priority[]).map(x => <option key={x} value={x}>{PRIORITY_LABEL[x]}</option>)}
            </select>
            <span className="muted small-text">Работали {relDate(p.last_activity)}</span>
          </div>
        </div>
        <div className="proj-actions">
          <button className="btn primary" onClick={notYet}><Play size={15} />Продолжить с Claude</button>
          <button className="btn" onClick={notYet}><Lightbulb size={15} />Обсудить идею</button>
          {primary && <button className="btn icon" title="Открыть папку" aria-label="Открыть папку" onClick={() => openPath(primary.path)}><FolderOpen size={16} /></button>}
        </div>
      </div>

      <div className="tabs" role="tablist">
        {([
          ['overview', 'Обзор', null],
          ['sessions', 'Сессии', p.session_count],
          ['agents', 'Агенты', p.agents.length + p.pinned_agents.length],
          ['recs', 'Доработки', p.open_recommendations],
          ['journal', 'Журнал', null],
        ] as [Tab, string, number | null][]).map(([k, label, n]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
            {label}{n ? <span className="n">{n}</span> : null}
          </button>
        ))}
      </div>

      {tab === 'overview' && <Overview p={p} save={save} openPath={openPath} setData={setData} onChanged={onChanged} />}
      {tab === 'sessions' && <Sessions projectId={id} onChanged={onChanged} />}
      {tab === 'agents' && <Agents p={p} setData={setData} openPath={openPath} />}
      {tab === 'recs' && <Recs projectId={id} onChanged={() => { onChanged(); api.get<ProjectDetail>(`/api/projects/${id}`).then(setData) }} />}
      {tab === 'journal' && <Journal p={p} />}
    </div>
  )
}

/* ---------- обзор ---------- */
function Overview({ p, save, openPath, setData, onChanged }: {
  p: ProjectDetail; save: (patch: Record<string, unknown>, ok?: string) => Promise<void>
  openPath: (path: string) => void; setData: (d: ProjectDetail) => void; onChanged: () => void
}) {
  const act = useAction()
  const [newPath, setNewPath] = useState('')
  const [linkOpen, setLinkOpen] = useState(false)
  const [tag, setTag] = useState('')
  const primary = p.paths.find(x => x.is_primary) ?? p.paths[0]

  const addPath = async () => {
    if (!newPath.trim()) return
    const r = await act(() => api.post<ProjectDetail>(`/api/projects/${p.id}/paths`, { path: newPath.trim() }), 'Папка добавлена')
    if (r) { setData(r); setNewPath(''); onChanged() }
  }
  const removePath = async (pathId: number) => {
    const r = await act(() => api.del<ProjectDetail>(`/api/projects/${p.id}/paths/${pathId}`))
    if (r) { setData(r); onChanged() }
  }
  const addTag = () => {
    const t = tag.trim()
    if (t && !p.tags.includes(t)) save({ tags: [...p.tags, t] })
    setTag('')
  }

  return (
    <div className="overview">
      <div>
        <div className="sheet">
          <h4>Где остановился</h4>
          <div className="next-step-box">
            <EditableText value={p.next_step} onSave={v => save({ next_step: v })} multiline
              placeholder="С чего начать в следующий раз" ariaLabel="Где остановился" />
          </div>
        </div>
        <div className="sheet">
          <h4>Мои мысли и пожелания</h4>
          <EditableText value={p.thoughts} onSave={v => save({ thoughts: v })} multiline className="thoughts"
            placeholder="Что хочется добавить, как должно выглядеть, что смущает" ariaLabel="Мысли и пожелания" />
        </div>
        <div className="sheet">
          <h4>О проекте</h4>
          <EditableText value={p.description} onSave={v => save({ description: v })} multiline
            placeholder="Коротко: что это и для кого" ariaLabel="Описание" />
          <div className="row" style={{ marginTop: 12 }}>
            {p.tags.map(t => (
              <span key={t} className="chip">{t}
                <button className="btn ghost small icon" style={{ width: 18, height: 18 }} aria-label={`Убрать тег ${t}`}
                  onClick={() => save({ tags: p.tags.filter(x => x !== t) })}><X size={12} /></button>
              </span>
            ))}
            <input className="input" style={{ width: 160, height: 28, padding: '2px 8px' }} placeholder="Добавить тег"
              value={tag} onChange={e => setTag(e.target.value)} onKeyDown={e => e.key === 'Enter' && addTag()} onBlur={addTag} />
          </div>
        </div>
      </div>

      <div>
        <div className="sheet">
          <h4>Папки</h4>
          {p.paths.length === 0 && <p className="muted small-text" style={{ marginTop: 0 }}>Добавьте папку проекта: по ней студия найдёт сессии Claude Code, CLAUDE.md и git.</p>}
          <div className="list">
            {p.paths.map(x => (
              <div key={x.id} className="list-item">
                <div className="body">
                  <div className="mono-path">{x.path}</div>
                  <div className="sub">
                    {x.is_primary && <span>основная</span>}
                    {x.exists === false && <span className="stale-note">папки нет на диске</span>}
                    {x.git && <span><GitBranch size={12} style={{ verticalAlign: -1 }} /> {x.git.branch ?? '—'}{x.git.dirty ? ', есть несохранённые изменения' : ''}</span>}
                    {x.claude_md && <button className="btn ghost small" style={{ height: 20, padding: '0 4px' }} onClick={() => openPath(x.claude_md!.path)}><FileText size={12} />CLAUDE.md</button>}
                  </div>
                </div>
                <div className="tools">
                  <button className="btn ghost small icon" aria-label="Открыть папку" title="Открыть папку" onClick={() => openPath(x.path)}><FolderOpen size={14} /></button>
                  <button className="btn ghost small icon" aria-label="Отвязать папку" title="Отвязать папку" onClick={() => removePath(x.id)}><X size={14} /></button>
                </div>
              </div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <input className="input" style={{ flex: 1 }} placeholder="C:\путь\к\папке" value={newPath}
              onChange={e => setNewPath(e.target.value)} onKeyDown={e => e.key === 'Enter' && addPath()} />
            <button className="btn" onClick={addPath}>Добавить</button>
          </div>
        </div>

        <div className="sheet">
          <h4>Чаты на claude.ai<button className="btn ghost small act" onClick={() => setLinkOpen(true)}><Plus size={14} />Ссылка</button></h4>
          {p.claude_ai_links.length === 0
            ? <p className="muted small-text" style={{ margin: 0 }}>Сохраните ссылки на проекты и чаты claude.ai, связанные с этой работой.</p>
            : <div className="list">{p.claude_ai_links.map((l, i) => (
              <div key={i} className="list-item">
                <div className="body"><a href={l.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{l.title || l.url}</a></div>
                <button className="btn ghost small icon" aria-label="Удалить ссылку" onClick={() => save({ claude_ai_links: p.claude_ai_links.filter((_, j) => j !== i) })}><X size={14} /></button>
              </div>))}</div>}
        </div>

        {primary?.claude_md && (
          <div className="sheet">
            <h4>Из CLAUDE.md</h4>
            <p className="small-text" style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--ink-2)' }}>{primary.claude_md.summary}</p>
          </div>
        )}
      </div>
      {linkOpen && <LinkDialog onClose={() => setLinkOpen(false)} onAdd={l => { setLinkOpen(false); save({ claude_ai_links: [...p.claude_ai_links, l] }) }} />}
    </div>
  )
}

function LinkDialog({ onClose, onAdd }: { onClose: () => void; onAdd: (l: Link) => void }) {
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [err, setErr] = useState('')
  const submit = () => {
    if (!/^https?:\/\//.test(url.trim())) { setErr('Вставьте ссылку, которая начинается с https://'); return }
    onAdd({ title: title.trim(), url: url.trim() })
  }
  return (
    <Dialog title="Ссылка на claude.ai" onClose={onClose}>
      <label className="field"><span>Ссылка</span>
        <input className="input" value={url} onChange={e => { setUrl(e.target.value); setErr('') }} placeholder="https://claude.ai/project/…" />
        {err && <span style={{ color: 'var(--pen)', fontSize: 13 }}>{err}</span>}
      </label>
      <label className="field"><span>Название</span>
        <input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="Обсуждение структуры атласа" onKeyDown={e => e.key === 'Enter' && submit()} />
      </label>
      <div className="actions"><button className="btn ghost" onClick={onClose}>Отмена</button><button className="btn primary" onClick={submit}>Добавить ссылку</button></div>
    </Dialog>
  )
}

/* ---------- сессии ---------- */
export function SessionRow({ s, projects, onChanged, showProject }: {
  s: SessionItem; projects?: ProjectCard[]; onChanged: () => void; showProject?: boolean
}) {
  const act = useAction()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const patch = async (body: Record<string, unknown>, ok?: string) => {
    if (await act(() => api.patch(`/api/sessions/${s.id}`, body), ok)) onChanged()
  }
  return (
    <div className="list-item">
      <div className="body">
        {editing
          ? <EditableText value={s.user_title || s.display_title} onSave={v => { setEditing(false); patch({ user_title: v }) }} ariaLabel="Название сессии" />
          : <div className="title" onDoubleClick={() => setEditing(true)} title="Двойной щелчок — переименовать">{s.display_title}</div>}
        {s.first_prompt && s.first_prompt !== s.display_title && <div className="prompt">{s.first_prompt}</div>}
        <div className="sub">
          <span>{fullDate(s.ended_at)}</span>
          {duration(s.started_at, s.ended_at) && <span>{duration(s.started_at, s.ended_at)}</span>}
          <span>{nPrompts(s.prompt_count)}</span>
          {s.git_branch && <span><GitBranch size={11} style={{ verticalAlign: -1 }} /> {s.git_branch}</span>}
          {s.entrypoint === 'claude-desktop' && <span>из приложения</span>}
          {s.file_missing && <span className="stale-note" title="Claude Code удаляет сессии старше 30 дней">файл удалён Claude Code</span>}
          {showProject && <span>{s.project_name ? `проект: ${s.project_name}` : 'без проекта'}</span>}
          {s.project_manual && <span>привязана вручную</span>}
        </div>
      </div>
      <div className="tools">
        {projects && (
          <select className="select" style={{ width: 170, height: 28, padding: '2px 6px', fontSize: 13 }} aria-label="Проект сессии"
            value={s.project_id ?? ''} onChange={e => patch({ binding: 'manual', project_id: e.target.value ? Number(e.target.value) : null }, 'Сессия перенесена')}>
            <option value="">Без проекта</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        {s.project_manual && <button className="btn ghost small icon" title="Вернуть автопривязку по папке" aria-label="Вернуть автопривязку" onClick={() => patch({ binding: 'auto' })}><RotateCcw size={14} /></button>}
        <button className="btn small" disabled={!s.can_resume} title={s.can_resume ? 'Открыть сессию в терминале' : 'Файл сессии удалён, продолжить нельзя'}
          onClick={() => toast('Открытие сессии появится на следующем этапе')}><Play size={13} />Открыть</button>
      </div>
    </div>
  )
}

function Sessions({ projectId, onChanged }: { projectId: number; onChanged: () => void }) {
  const { data, reload } = useLoad(() => Promise.all([
    api.get<SessionItem[]>(`/api/projects/${projectId}/sessions`),
    api.get<ProjectCard[]>('/api/projects'),
  ]), [projectId])
  if (!data) return null
  const [sessions, projects] = data
  if (sessions.length === 0) {
    return <EmptyState title="Сессий пока нет" text="Сессии появятся, когда вы поработаете с Claude Code в папке проекта. Чужие сессии можно перенести сюда из раздела «Сессии» или «Разобрать»." />
  }
  return (
    <div className="sheet"><div className="list">
      {sessions.map(s => <SessionRow key={s.id} s={s} projects={projects} onChanged={() => { reload(); onChanged() }} />)}
    </div></div>
  )
}

/* ---------- агенты ---------- */
const KIND_LABEL = { agent: 'Агенты', skill: 'Скиллы', mcp: 'MCP-серверы' } as const

function Agents({ p, setData, openPath }: { p: ProjectDetail; setData: (d: ProjectDetail) => void; openPath: (path: string) => void }) {
  const act = useAction()
  const [picking, setPicking] = useState(false)
  const unpin = async (fp: string) => {
    const r = await act(() => api.del<ProjectDetail>(`/api/projects/${p.id}/pins?file_path=${encodeURIComponent(fp)}`))
    if (r) setData(r)
  }
  const groups = (['agent', 'skill', 'mcp'] as const).map(k => [k, p.agents.filter(a => a.kind === k)] as const).filter(([, xs]) => xs.length)
  return (
    <div className="overview">
      <div className="sheet">
        <h4>Найдены в папке проекта</h4>
        {groups.length === 0 && <p className="muted small-text" style={{ margin: 0 }}>В папке .claude проекта нет агентов и скиллов, а в .mcp.json — серверов.</p>}
        {groups.map(([k, xs]) => (
          <details key={k} className="kind-group" open={xs.length <= 12}>
            <summary>{KIND_LABEL[k]} <span className="chip">{xs.length}</span></summary>
            {xs.map(a => <AgentRow key={`${a.kind}:${a.name}`} a={a} openPath={openPath} />)}
          </details>
        ))}
      </div>
      <div className="sheet">
        <h4>Закреплены за проектом<button className="btn ghost small act" onClick={() => setPicking(true)}><Pin size={14} />Закрепить</button></h4>
        {p.pinned_agents.length === 0
          ? <p className="muted small-text" style={{ margin: 0 }}>Общие агенты и скиллы из вашего профиля, которыми вы пользуетесь в этом проекте.</p>
          : p.pinned_agents.map(a => (
            <AgentRow key={a.file_path} a={a} openPath={openPath}
              extra={<button className="btn ghost small icon" aria-label="Открепить" title="Открепить" onClick={() => unpin(a.file_path!)}><PinOff size={14} /></button>} />
          ))}
      </div>
      {picking && <PinDialog p={p} onClose={() => setPicking(false)} onPinned={d => setData(d)} />}
    </div>
  )
}

function AgentRow({ a, openPath, extra }: { a: Agent; openPath: (p: string) => void; extra?: React.ReactNode }) {
  return (
    <div className="agent-row">
      <span className="name">{a.name}{a.missing && <span className="stale-note small-text"> (файл не найден)</span>}</span>
      <span className="d">{a.description}{a.model ? ` · модель ${a.model}` : ''}</span>
      {a.file_path && a.kind !== 'mcp' && <button className="btn ghost small icon" aria-label="Открыть файл" title="Открыть файл" onClick={() => openPath(a.file_path!)}><ExternalLink size={13} /></button>}
      {extra}
    </div>
  )
}

function PinDialog({ p, onClose, onPinned }: { p: ProjectDetail; onClose: () => void; onPinned: (d: ProjectDetail) => void }) {
  const { data } = useLoad(() => api.get<Agent[]>('/api/agents'), [])
  const act = useAction()
  const pinned = new Set(p.pinned_agents.map(a => a.file_path))
  const pin = async (fp: string) => {
    const r = await act(() => api.post<ProjectDetail>(`/api/projects/${p.id}/pins`, { file_path: fp }))
    if (r) onPinned(r)
  }
  return (
    <Dialog title="Закрепить общий агент или скилл" onClose={onClose}>
      <div style={{ maxHeight: '50vh', overflow: 'auto' }}>
        {data?.length === 0 && <p className="muted">В профиле нет общих агентов и скиллов.</p>}
        {data?.map(a => (
          <div key={a.file_path} className="agent-row">
            <span className="name">{a.name}</span>
            <span className="d">{KIND_LABEL[a.kind]}. {a.description}</span>
            <button className="btn small" disabled={pinned.has(a.file_path)} onClick={() => pin(a.file_path!)}>{pinned.has(a.file_path) ? 'Закреплён' : 'Закрепить'}</button>
          </div>
        ))}
      </div>
      <div className="actions"><button className="btn" onClick={onClose}>Готово</button></div>
    </Dialog>
  )
}

/* ---------- доработки ---------- */
function Recs({ projectId, onChanged }: { projectId: number; onChanged: () => void }) {
  const [filter, setFilter] = useState<'active' | RecStatus | 'all'>('active')
  const { data, reload } = useLoad(() => api.get<Recommendation[]>(`/api/projects/${projectId}/recommendations`), [projectId])
  const [text, setText] = useState('')
  const [prio, setPrio] = useState<Priority>('normal')
  const act = useAction()
  const changed = () => { reload(); onChanged() }
  const add = async () => {
    if (!text.trim()) return
    if (await act(() => api.post(`/api/projects/${projectId}/recommendations`, { text: text.trim(), priority: prio }))) { setText(''); changed() }
  }
  const patch = async (id: number, body: Record<string, unknown>) => { if (await act(() => api.patch(`/api/recommendations/${id}`, body))) changed() }
  const remove = async (id: number) => { await act(() => api.del(`/api/recommendations/${id}`)); changed() }
  const items = (data ?? []).filter(r => filter === 'all' || (filter === 'active' ? r.status === 'open' || r.status === 'in_progress' : r.status === filter))
  const order: Record<Priority, number> = { high: 0, normal: 1, low: 2 }
  items.sort((a, b) => order[a.priority] - order[b.priority])

  return (
    <div className="sheet">
      <div className="row" style={{ marginBottom: 6 }}>
        <input className="input" style={{ flex: 1, minWidth: 240 }} placeholder="Что доработать" value={text}
          onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} />
        <select className="select" style={{ width: 'auto' }} value={prio} onChange={e => setPrio(e.target.value as Priority)} aria-label="Приоритет">
          {(['high', 'normal', 'low'] as Priority[]).map(x => <option key={x} value={x}>{PRIORITY_LABEL[x]}</option>)}
        </select>
        <button className="btn primary" onClick={add}><Plus size={15} />Добавить</button>
      </div>
      <div className="row" style={{ margin: '12px 0 4px' }}>
        <div className="seg" role="group" aria-label="Фильтр">
          {([['active', 'Активные'], ['done', 'Сделано'], ['rejected', 'Отклонённые'], ['all', 'Все']] as const).map(([k, l]) =>
            <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{l}</button>)}
        </div>
      </div>
      {data && items.length === 0 && <p className="muted" style={{ padding: '14px 2px 0' }}>{filter === 'active' ? 'Открытых доработок нет.' : 'Здесь пусто.'}</p>}
      <div className="list">
        {items.map(r => (
          <div key={r.id} className={`list-item${r.status === 'done' || r.status === 'rejected' ? ' done' : ''}`}>
            <input type="checkbox" className="rec-check" checked={r.status === 'done'} aria-label="Сделано"
              onChange={e => patch(r.id, { status: e.target.checked ? 'done' : 'open' })} />
            <div className="body">
              <div className="title">{r.text}</div>
              <div className="sub">
                <span className={r.priority === 'high' ? 'prio-high' : ''}>{PRIORITY_LABEL[r.priority]}</span>
                {r.source === 'claude' && <span className="chip accent">предложил Claude</span>}
                <span>{relDate(r.created_at)}</span>
              </div>
            </div>
            <div className="tools">
              <select className="select" style={{ width: 'auto', height: 28, padding: '2px 6px', fontSize: 13 }} value={r.status} aria-label="Статус"
                onChange={e => patch(r.id, { status: e.target.value })}>
                {(Object.keys(REC_STATUS_LABEL) as RecStatus[]).map(s => <option key={s} value={s}>{REC_STATUS_LABEL[s]}</option>)}
              </select>
              <button className="btn ghost small icon danger" aria-label="Удалить" title="Удалить" onClick={() => remove(r.id)}><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---------- журнал ---------- */
function Journal({ p }: { p: ProjectDetail }) {
  const { data, reload } = useLoad(() => Promise.all([
    api.get<ActivityEntry[]>(`/api/projects/${p.id}/activity`),
    api.get<StageEntry[]>(`/api/projects/${p.id}/stages`),
  ]), [p.id])
  const [text, setText] = useState('')
  const act = useAction()
  const add = async () => {
    if (!text.trim()) return
    if (await act(() => api.post(`/api/projects/${p.id}/activity`, { text: text.trim() }))) { setText(''); reload() }
  }
  const remove = async (id: number) => { await act(() => api.del(`/api/activity/${id}`)); reload() }
  const commits = p.paths.flatMap(x => x.git?.commits ?? []).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8)
  const [activity, stages] = data ?? [[], []]

  return (
    <div className="overview">
      <div className="sheet">
        <h4>Что сделано</h4>
        <div className="row" style={{ marginBottom: 14 }}>
          <input className="input" style={{ flex: 1 }} placeholder="Выгрузил свод КТП в Word" value={text}
            onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} />
          <button className="btn" onClick={add}>Записать</button>
        </div>
        {activity.length === 0
          ? <p className="muted small-text" style={{ margin: 0 }}>Записывайте сюда итоги работы. Позже это будет делать и сам Claude в конце сессии.</p>
          : <ul className="timeline">{activity.map(a => (
            <li key={a.id}>
              <div className="when">{fullDate(a.date)}{a.source === 'claude' ? ' · записал Claude' : ''}
                <button className="btn ghost small icon" style={{ width: 20, height: 20, marginLeft: 6 }} aria-label="Удалить запись" onClick={() => remove(a.id)}><X size={12} /></button>
              </div>
              <div>{a.text}</div>
            </li>))}</ul>}
      </div>
      <div>
        <div className="sheet">
          <h4>Стадии</h4>
          <ul className="timeline">
            {[...stages].reverse().map(s => (
              <li key={s.id}>
                <div className="when">{fullDate(s.date)}</div>
                <div>{s.from_stage ? `${STAGE_LABEL[s.from_stage]} → ${STAGE_LABEL[s.to_stage]}` : `Создан: ${STAGE_LABEL[s.to_stage]}`}</div>
                {s.comment && s.comment !== 'Создан' && <div className="muted small-text">{s.comment}</div>}
              </li>))}
          </ul>
        </div>
        <div className="sheet">
          <h4>Последние коммиты</h4>
          {commits.length === 0
            ? <p className="muted small-text" style={{ margin: 0 }}>У папок проекта нет своего git-репозитория.</p>
            : <div className="list">{commits.map(c => (
              <div key={c.hash} className="list-item" style={{ padding: '8px 0' }}>
                <div className="body"><div>{c.subject}</div><div className="sub"><span>{relDate(c.date)}</span><span>{c.hash}</span></div></div>
              </div>))}</div>}
        </div>
      </div>
    </div>
  )
}

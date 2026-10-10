import { Check, ChevronLeft, ExternalLink, FileText, FolderOpen, GitBranch, ImagePlus, Lightbulb, Pin, PinOff, Play, Plus, RotateCcw, Trash2, X } from 'lucide-react'
import { useRef, useState, type CSSProperties } from 'react'
import { api, assetUrl } from '../api'
import { Cover } from '../Cover'
import { COLORS, ICONS, projectTheme } from '../theme'
import type { ActivityEntry, Agent, Link, Priority, ProjectCard, ProjectDetail, RecStatus, Recommendation, SessionItem, Stage, StageEntry } from '../types'
import { Alert, EditableText, EmptyState, Progress, Section, Sheet, useAction, useLoad, useToast } from '../ui'
import { PRIORITY_LABEL, REC_STATUS_LABEL, STAGES, STAGE_LABEL, duration, fullDate, nPrompts, relDate } from '../util'
import { NewProjectSheet, STAGE_COLOR, Tile } from './Projects'

type Tab = 'overview' | 'sessions' | 'agents' | 'recs' | 'journal'

export function ProjectPage({ id, back, open, onChanged }: { id: number; back: () => void; open: (id: number) => void; onChanged: () => void }) {
  const { data: p, setData, error, reload } = useLoad(() => api.get<ProjectDetail>(`/api/projects/${id}`), [id])
  const { data: all } = useLoad(() => api.get<ProjectCard[]>('/api/projects', ), [id])
  const [tab, setTab] = useState<Tab>('overview')
  const [coverOpen, setCoverOpen] = useState(false)
  const act = useAction()
  const toast = useToast()

  if (error) return <div className="page"><button className="btn plain" onClick={back}><ChevronLeft size={18} />Проекты</button><EmptyState title="Проект не открылся" text={error} /></div>
  if (!p) return <div className="page" />

  const theme = projectTheme(p)
  const save = async (patch: Record<string, unknown>, ok?: string) => {
    const r = await act(() => api.patch<ProjectDetail>(`/api/projects/${id}`, patch), ok)
    if (r) { setData(r); onChanged() }
  }
  const primary = p.paths.find(x => x.is_primary) ?? p.paths[0]
  const openPath = (path: string) => act(() => api.post('/api/open', { path }))
  const notYet = () => toast('Запуск Claude появится на следующем этапе')

  return (
    <div className="page" style={{ '--tint': theme.color } as CSSProperties}>
      <div className="hero">
        <Cover p={p} parts={p.parts} showIcon={false} />
        <div className="hero-shade" />
        <div className="hero-top">
          <button className="hero-btn" onClick={p.parent_id ? () => open(p.parent_id!) : back}><ChevronLeft size={18} />{p.parent_name ?? 'Проекты'}</button>
          <button className="hero-btn" onClick={() => setCoverOpen(true)}><ImagePlus size={16} />Обложка</button>
        </div>
        <div className="hero-text">
          {p.parent_name && <button className="crumb" onClick={() => open(p.parent_id!)}>Часть проекта «{p.parent_name}»</button>}
          <EditableText value={p.name} onSave={v => v && save({ name: v })} className="hero-title" ariaLabel="Название проекта" />
        </div>
      </div>

      <div className="actions-row">
        <button className="btn filled large" onClick={notYet}><Play size={17} fill="currentColor" />Продолжить с Claude</button>
        <button className="btn large" onClick={notYet}><Lightbulb size={17} />Обсудить идею</button>
        <span className="spacer" />
        {primary && <button className="btn circle gray" title="Открыть папку" aria-label="Открыть папку" onClick={() => openPath(primary.path)}><FolderOpen size={17} /></button>}
      </div>

      <div className="status-row">
        <select className="select compact" value={p.stage} aria-label="Стадия"
          style={{ color: STAGE_COLOR[p.stage], fontWeight: 600, background: 'var(--fill-2)' }}
          onChange={e => save({ stage: e.target.value as Stage }, `Стадия: ${STAGE_LABEL[e.target.value as Stage]}`)}>
          {[...STAGES, { id: 'archived' as Stage, label: 'В архиве' }].map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <Progress big value={p.progress} onChange={v => save({ progress: v })} />
        <select className="select compact" value={p.priority} aria-label="Приоритет" onChange={e => save({ priority: e.target.value as Priority })}>
          {(['high', 'normal', 'low'] as Priority[]).map(x => <option key={x} value={x}>{PRIORITY_LABEL[x]}</option>)}
        </select>
        <span className="muted small-text">Работали {relDate(p.last_activity)}</span>
      </div>

      <div className="segmented" role="tablist" style={{ marginBottom: 22 }}>
        {([
          ['overview', 'Обзор', null],
          ['sessions', 'Сессии', p.session_count],
          ['agents', 'Агенты', p.agents.length + p.pinned_agents.length],
          ['recs', 'Доработки', p.open_recommendations],
          ['journal', 'Журнал', null],
        ] as [Tab, string, number | null][]).map(([k, label, n]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{label}{n ? <span className="n">{n}</span> : null}</button>
        ))}
      </div>

      {tab === 'overview' && <Overview p={p} all={all ?? []} save={save} openPath={openPath} setData={setData} onChanged={onChanged}
        open={open} onDeleted={() => { onChanged(); back() }} reload={reload} />}
      {tab === 'sessions' && <Sessions projectId={id} onChanged={onChanged} hasParts={p.parts.length > 0} />}
      {tab === 'agents' && <Agents p={p} setData={setData} openPath={openPath} />}
      {tab === 'recs' && <Recs projectId={id} onChanged={() => { onChanged(); reload() }} />}
      {tab === 'journal' && <Journal p={p} />}

      {coverOpen && <CoverSheet p={p} onClose={() => setCoverOpen(false)} onSaved={d => { setData(d); onChanged() }} save={save} />}
    </div>
  )
}

/* ---------- обзор ---------- */
function Overview({ p, all, save, openPath, setData, onChanged, open, onDeleted, reload }: {
  p: ProjectDetail; all: ProjectCard[]; save: (patch: Record<string, unknown>, ok?: string) => Promise<void>
  openPath: (path: string) => void; setData: (d: ProjectDetail) => void; onChanged: () => void
  open: (id: number) => void; onDeleted: () => void; reload: () => void
}) {
  const act = useAction()
  const [newPath, setNewPath] = useState('')
  const [linkOpen, setLinkOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [addingPart, setAddingPart] = useState(false)
  const [tag, setTag] = useState('')
  const primary = p.paths.find(x => x.is_primary) ?? p.paths[0]
  const canHaveParts = !p.parent_id
  const canBePart = p.parts.length === 0
  const others = all.filter(x => x.id !== p.id)

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
  const attachPart = async (childId: number) => {
    if (await act(() => api.patch(`/api/projects/${childId}`, { parent_id: p.id }), 'Проект стал частью')) { reload(); onChanged() }
  }
  const remove = async () => {
    const ok = await act(() => api.del(`/api/projects/${p.id}`).then(() => true), `Проект «${p.name}» удалён`)
    setDeleting(false)
    if (ok) onDeleted()
  }

  return (
    <div className="cols">
      <div>
        <Section title="Где остановился" foot="С чего начать в следующий раз. Claude увидит это при запуске из Студии.">
          <div className="pad"><EditableText value={p.next_step} onSave={v => save({ next_step: v })} multiline placeholder="Например: доделать выгрузку КТП в Word" ariaLabel="Где остановился" /></div>
        </Section>
        <Section title="Мои мысли и пожелания">
          <div className="pad"><EditableText value={p.thoughts} onSave={v => save({ thoughts: v })} multiline className="thoughts"
            placeholder="Что хочется добавить, как должно выглядеть, что смущает" ariaLabel="Мысли и пожелания" /></div>
        </Section>
        {canHaveParts && (p.parts.length > 0 || others.some(o => !o.parent_id && o.children.length === 0)) && (
          <section className="section">
            <h3 className="section-title">Части проекта
              <span className="act"><button className="btn small" onClick={() => setAddingPart(true)}><Plus size={14} />Новая часть</button></span>
            </h3>
            {p.parts.length > 0 && (
              <div className="parts">{p.parts.map(c => <Tile key={c.id} p={c} all={all} onOpen={() => open(c.id)} />)}</div>
            )}
            <div className="row" style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12, flexWrap: 'wrap' }}>
              <select className="select compact" value="" aria-label="Сделать существующий проект частью"
                onChange={e => e.target.value && attachPart(Number(e.target.value))}>
                <option value="">Добавить существующий проект…</option>
                {others.filter(o => !o.parent_id && o.children.length === 0).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
          </section>
        )}
        <Section title="О проекте">
          <div className="pad">
            <EditableText value={p.description} onSave={v => save({ description: v })} multiline placeholder="Коротко: что это и для кого" ariaLabel="Описание" />
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginTop: 12 }}>
              {p.tags.map(t => (
                <span key={t} className="capsule tinted">{t}
                  <button className="btn plain" style={{ minHeight: 18, padding: 0 }} aria-label={`Убрать тег ${t}`} onClick={() => save({ tags: p.tags.filter(x => x !== t) })}><X size={12} /></button>
                </span>
              ))}
              <input className="input" style={{ width: 150, minHeight: 28, padding: '2px 10px' }} placeholder="Добавить тег"
                value={tag} onChange={e => setTag(e.target.value)} onKeyDown={e => e.key === 'Enter' && addTag()} onBlur={addTag} />
            </div>
          </div>
        </Section>
      </div>

      <div>
        <Section title="Папки" foot={p.paths.length ? undefined : 'По папке Студия находит сессии Claude Code, CLAUDE.md, git и картинку для обложки.'}>
          {p.paths.map(x => (
            <div key={x.id} className="cell">
              <div className="body">
                <div className="title strong">{x.path.split(/[\\/]/).pop()}</div>
                <div className="mono-path">{x.path}</div>
                <div className="sub">
                  {x.exists === false && <span className="warn">папки нет на диске</span>}
                  {x.git && <span><GitBranch size={12} style={{ verticalAlign: -1 }} /> {x.git.branch ?? '—'}{x.git.dirty ? ', есть несохранённые изменения' : ''}</span>}
                  {x.claude_md && <button className="btn plain small" style={{ minHeight: 20, padding: 0 }} onClick={() => openPath(x.claude_md!.path)}><FileText size={12} />CLAUDE.md</button>}
                </div>
              </div>
              <div className="tools">
                <button className="btn small circle gray" aria-label="Открыть папку" title="Открыть папку" onClick={() => openPath(x.path)}><FolderOpen size={15} /></button>
                <button className="btn small circle gray" aria-label="Отвязать папку" title="Отвязать папку" onClick={() => removePath(x.id)}><X size={15} /></button>
              </div>
            </div>
          ))}
          <div className="cell">
            <input className="input" style={{ flex: 1 }} placeholder="C:\путь\к\папке" value={newPath}
              onChange={e => setNewPath(e.target.value)} onKeyDown={e => e.key === 'Enter' && addPath()} aria-label="Новая папка" />
            <button className="btn small" onClick={addPath}>Добавить</button>
          </div>
        </Section>

        <Section title="Чаты на claude.ai" action={<button className="btn small" onClick={() => setLinkOpen(true)}><Plus size={14} />Ссылка</button>}
          foot={p.claude_ai_links.length ? undefined : 'Ссылки на проекты и чаты claude.ai, связанные с этой работой.'}>
          {p.claude_ai_links.map((l, i) => (
            <div key={i} className="cell">
              <div className="body"><a href={l.url} target="_blank" rel="noreferrer" style={{ color: 'var(--blue)', textDecoration: 'none' }}>{l.title || l.url}</a></div>
              <button className="btn small circle gray" aria-label="Удалить ссылку" onClick={() => save({ claude_ai_links: p.claude_ai_links.filter((_, j) => j !== i) })}><X size={14} /></button>
            </div>
          ))}
        </Section>

        {primary?.claude_md && (
          <Section title="Из CLAUDE.md">
            <div className="pad small-text muted" style={{ whiteSpace: 'pre-wrap' }}>{primary.claude_md.summary}</div>
          </Section>
        )}

        {canBePart && (
          <Section title="Входит в проект" foot="Например, контент-завод и атлас — части «Истории зашла».">
            <div className="cell">
              <select className="select" value={p.parent_id ?? ''} aria-label="Родительский проект"
                onChange={e => save({ parent_id: e.target.value ? Number(e.target.value) : null }, e.target.value ? 'Проект стал частью' : 'Проект стал самостоятельным')}>
                <option value="">Самостоятельный проект</option>
                {others.filter(o => !o.parent_id).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
          </Section>
        )}

        <Section foot="Удаляется только карточка в Студии. Папки, код и сессии Claude Code остаются.">
          <button className="cell button" style={{ color: 'var(--red)', width: '100%', border: 0, background: 'none', font: 'inherit' }} onClick={() => setDeleting(true)}>
            <Trash2 size={17} />Удалить проект
          </button>
        </Section>
      </div>

      {linkOpen && <LinkSheet onClose={() => setLinkOpen(false)} onAdd={l => { setLinkOpen(false); save({ claude_ai_links: [...p.claude_ai_links, l] }) }} />}
      {addingPart && <NewProjectSheet projects={all} initial={{ parent_id: p.id }} onClose={() => setAddingPart(false)}
        onCreated={c => { setAddingPart(false); onChanged(); open(c.id) }} />}
      {deleting && <Alert title={`Удалить «${p.name}»?`}
        text={`Описание, мысли, доработки и журнал удалятся из Студии навсегда.${p.parts.length ? ' Части проекта станут самостоятельными.' : ''} Папки и сессии Claude Code останутся.`}
        confirm="Удалить" onConfirm={remove} onClose={() => setDeleting(false)} />}
    </div>
  )
}

function LinkSheet({ onClose, onAdd }: { onClose: () => void; onAdd: (l: Link) => void }) {
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [err, setErr] = useState('')
  const submit = () => {
    if (!/^https?:\/\//.test(url.trim())) { setErr('Вставьте ссылку, которая начинается с https://'); return }
    onAdd({ title: title.trim(), url: url.trim() })
  }
  return (
    <Sheet title="Ссылка на claude.ai" onClose={onClose} done={submit} doneLabel="Добавить">
      <label className="field"><span>Ссылка</span>
        <input className="input" value={url} onChange={e => { setUrl(e.target.value); setErr('') }} placeholder="https://claude.ai/project/…" />
        {err && <span className="error-text">{err}</span>}
      </label>
      <label className="field"><span>Название</span>
        <input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="Обсуждение структуры атласа" onKeyDown={e => e.key === 'Enter' && submit()} />
      </label>
    </Sheet>
  )
}

/* ---------- обложка и оформление ---------- */
function CoverSheet({ p, onClose, onSaved, save }: {
  p: ProjectDetail; onClose: () => void; onSaved: (d: ProjectDetail) => void; save: (patch: Record<string, unknown>) => Promise<void>
}) {
  const { data: cands } = useLoad(() => api.get<{ path: string; name: string; size: number }[]>(`/api/projects/${p.id}/cover-candidates`), [p.id])
  const act = useAction()
  const file = useRef<HTMLInputElement>(null)
  const theme = projectTheme(p)
  const choose = async (path: string) => { const r = await act(() => api.put<ProjectDetail>(`/api/projects/${p.id}/cover`, { path }), 'Обложка выбрана'); if (r) onSaved(r) }
  const reset = async () => { const r = await act(() => api.del<ProjectDetail>(`/api/projects/${p.id}/cover`), 'Обложка по умолчанию'); if (r) onSaved(r) }
  const upload = async (f: File) => {
    if (f.size > 15 * 1024 * 1024) { act(() => Promise.reject(new Error('Картинка больше 15 МБ'))); return }
    const data = await new Promise<string>((res, rej) => {
      const r = new FileReader()
      r.onload = () => res(String(r.result).split(',')[1] ?? '')
      r.onerror = () => rej(r.error)
      r.readAsDataURL(f)
    })
    const d = await act(() => api.post<ProjectDetail>(`/api/projects/${p.id}/cover/upload`, { filename: f.name, data }), 'Обложка загружена')
    if (d) onSaved(d)
  }
  return (
    <Sheet title="Обложка и оформление" onClose={onClose} wide>
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 18, alignItems: 'start' }}>
        <Cover p={p} parts={p.parts} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p className="muted small-text" style={{ margin: 0 }}>Обложка показывает, что внутри: скриншот, карта, иллюстрация. Студия сама нашла картинки в папках проекта, можно выбрать свою.</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn" onClick={() => file.current?.click()}><ImagePlus size={16} />Выбрать файл</button>
            {(p.cover_is_custom || p.cover) && <button className="btn gray" onClick={reset}><RotateCcw size={15} />{p.cover_is_custom ? 'Вернуть по умолчанию' : 'Сбросить'}</button>}
          </div>
          <input ref={file} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden
            onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = '' }} />
        </div>
      </div>

      {cands && cands.length > 0 && (
        <div className="field"><span>Картинки из папок проекта</span>
          <div className="picker-grid">
            {cands.map(c => (
              <button key={c.path} title={c.name} aria-label={c.name} onClick={() => choose(c.path)}>
                <img src={assetUrl(`/api/image?path=${encodeURIComponent(c.path)}`)} alt="" loading="lazy" />
              </button>
            ))}
          </div>
        </div>
      )}
      {cands && cands.length === 0 && <p className="muted small-text" style={{ margin: 0 }}>В папках проекта подходящих картинок нет. Без картинки обложка рисуется цветом и значком.</p>}

      <div className="field"><span>Цвет проекта</span>
        <div className="swatches">
          {COLORS.map(c => <button key={c.hex} className="swatch" style={{ background: c.hex }} title={c.label} aria-label={c.label}
            aria-pressed={theme.color.toLowerCase() === c.hex.toLowerCase()} onClick={() => save({ color: c.hex })} />)}
          {p.color && <button className="btn small gray" onClick={() => save({ color: null })}>По смыслу</button>}
        </div>
      </div>
      <div className="field"><span>Значок</span>
        <div className="icon-choices" style={{ '--tint': theme.color } as CSSProperties}>
          {Object.entries(ICONS).map(([k, v]) => <button key={k} title={v.label} aria-label={v.label} aria-pressed={theme.icon === k} onClick={() => save({ icon: k })}><v.icon size={19} /></button>)}
        </div>
      </div>
    </Sheet>
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
    <div className="cell">
      <div className="body">
        {editing
          ? <EditableText value={s.user_title || s.display_title} onSave={v => { setEditing(false); patch({ user_title: v }) }} ariaLabel="Название сессии" />
          : <div className="title strong" onDoubleClick={() => setEditing(true)} title="Двойной щелчок — переименовать">{s.display_title}</div>}
        {s.first_prompt && s.first_prompt !== s.display_title && <div className="small-text muted" style={{ marginTop: 2 }}>{s.first_prompt}</div>}
        <div className="sub">
          <span>{fullDate(s.ended_at)}</span>
          {duration(s.started_at, s.ended_at) && <span>{duration(s.started_at, s.ended_at)}</span>}
          <span>{nPrompts(s.prompt_count)}</span>
          {s.git_branch && <span><GitBranch size={11} style={{ verticalAlign: -1 }} /> {s.git_branch}</span>}
          {s.file_missing && <span className="warn" title="Claude Code удаляет сессии старше 30 дней">файл удалён Claude Code</span>}
          {showProject && <span>{s.project_name ? `проект: ${s.project_name}` : 'без проекта'}</span>}
          {s.project_manual && <span>привязана вручную</span>}
        </div>
      </div>
      <div className="tools">
        {projects && (
          <select className="select compact" style={{ maxWidth: 190 }} aria-label="Проект сессии"
            value={s.project_id ?? ''} onChange={e => patch({ binding: 'manual', project_id: e.target.value ? Number(e.target.value) : null }, 'Сессия перенесена')}>
            <option value="">Без проекта</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.parent_name ? `${p.parent_name} › ` : ''}{p.name}</option>)}
          </select>
        )}
        {s.project_manual && <button className="btn small circle gray" title="Вернуть автопривязку по папке" aria-label="Вернуть автопривязку" onClick={() => patch({ binding: 'auto' })}><RotateCcw size={14} /></button>}
        <button className="btn small" disabled={!s.can_resume} title={s.can_resume ? 'Открыть сессию в терминале' : 'Файл сессии удалён, продолжить нельзя'}
          onClick={() => toast('Открытие сессии появится на следующем этапе')}><Play size={13} />Открыть</button>
      </div>
    </div>
  )
}

function Sessions({ projectId, onChanged, hasParts }: { projectId: number; onChanged: () => void; hasParts: boolean }) {
  const { data, reload } = useLoad(() => Promise.all([
    api.get<SessionItem[]>(`/api/projects/${projectId}/sessions`),
    api.get<ProjectCard[]>('/api/projects'),
  ]), [projectId])
  if (!data) return null
  const [sessions, projects] = data
  if (sessions.length === 0) {
    return <EmptyState title="Сессий пока нет" text={hasParts
      ? 'Сессии этого проекта лежат в его частях — откройте нужную часть.'
      : 'Сессии появятся, когда вы поработаете с Claude Code в папке проекта. Чужие сессии можно перенести сюда из раздела «Сессии» или «Разобрать».'} />
  }
  return <Section>{sessions.map(s => <SessionRow key={s.id} s={s} projects={projects} onChanged={() => { reload(); onChanged() }} />)}</Section>
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
    <div className="cols">
      <div>
        {groups.length === 0 && <EmptyState title="В папке проекта агентов нет" text="Агенты и скиллы лежат в папке .claude проекта, MCP-серверы — в .mcp.json." />}
        {groups.map(([k, xs]) => (
          <section key={k} className="section">
            <details className="kind-group" open={xs.length <= 12}>
              <summary className="section-title">{KIND_LABEL[k]} <span className="capsule">{xs.length}</span></summary>
              <div className="group">{xs.map(a => <AgentRow key={`${a.kind}:${a.name}`} a={a} openPath={openPath} />)}</div>
            </details>
          </section>
        ))}
      </div>
      <div>
        <Section title="Закреплены за проектом" action={<button className="btn small" onClick={() => setPicking(true)}><Pin size={14} />Закрепить</button>}
          foot={p.pinned_agents.length ? undefined : 'Общие агенты и скиллы из вашего профиля, которыми вы пользуетесь в этом проекте.'}>
          {p.pinned_agents.map(a => (
            <AgentRow key={a.file_path} a={a} openPath={openPath}
              extra={<button className="btn small circle gray" aria-label="Открепить" title="Открепить" onClick={() => unpin(a.file_path!)}><PinOff size={14} /></button>} />
          ))}
        </Section>
      </div>
      {picking && <PinSheet p={p} onClose={() => setPicking(false)} onPinned={d => setData(d)} />}
    </div>
  )
}

function AgentRow({ a, openPath, extra }: { a: Agent; openPath: (p: string) => void; extra?: React.ReactNode }) {
  return (
    <div className="cell">
      <div className="body">
        <div className="title strong">{a.name}{a.missing && <span className="warn small-text"> (файл не найден)</span>}</div>
        {a.description && <div className="agent-desc">{a.description}{a.model ? ` · модель ${a.model}` : ''}</div>}
      </div>
      <div className="tools">
        {a.file_path && a.kind !== 'mcp' && <button className="btn small circle gray" aria-label="Открыть файл" title="Открыть файл" onClick={() => openPath(a.file_path!)}><ExternalLink size={14} /></button>}
        {extra}
      </div>
    </div>
  )
}

function PinSheet({ p, onClose, onPinned }: { p: ProjectDetail; onClose: () => void; onPinned: (d: ProjectDetail) => void }) {
  const { data } = useLoad(() => api.get<Agent[]>('/api/agents'), [])
  const act = useAction()
  const pinned = new Set(p.pinned_agents.map(a => a.file_path))
  const pin = async (fp: string) => {
    const r = await act(() => api.post<ProjectDetail>(`/api/projects/${p.id}/pins`, { file_path: fp }))
    if (r) onPinned(r)
  }
  return (
    <Sheet title="Закрепить агент или скилл" onClose={onClose}>
      {data?.length === 0 && <p className="muted">В профиле нет общих агентов и скиллов.</p>}
      <div className="group">
        {data?.map(a => (
          <div key={a.file_path} className="cell">
            <div className="body"><div className="title strong">{a.name}</div><div className="agent-desc">{KIND_LABEL[a.kind]}. {a.description}</div></div>
            <button className="btn small" disabled={pinned.has(a.file_path)} onClick={() => pin(a.file_path!)}>{pinned.has(a.file_path) ? 'Закреплён' : 'Закрепить'}</button>
          </div>
        ))}
      </div>
    </Sheet>
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
  const order: Record<Priority, number> = { high: 0, normal: 1, low: 2 }
  const items = (data ?? []).filter(r => filter === 'all' || (filter === 'active' ? r.status === 'open' || r.status === 'in_progress' : r.status === filter))
    .sort((a, b) => order[a.priority] - order[b.priority])

  return (
    <div style={{ maxWidth: 820 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input className="input" style={{ flex: 1, minWidth: 220 }} placeholder="Что доработать" value={text}
          onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} />
        <select className="select compact" style={{ minHeight: 40 }} value={prio} onChange={e => setPrio(e.target.value as Priority)} aria-label="Приоритет">
          {(['high', 'normal', 'low'] as Priority[]).map(x => <option key={x} value={x}>{PRIORITY_LABEL[x]}</option>)}
        </select>
        <button className="btn filled" style={{ minHeight: 40 }} onClick={add}><Plus size={16} />Добавить</button>
      </div>
      <div className="segmented" role="group" aria-label="Фильтр" style={{ marginBottom: 14 }}>
        {([['active', 'Активные'], ['done', 'Сделано'], ['rejected', 'Отклонённые'], ['all', 'Все']] as const).map(([k, l]) =>
          <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{l}</button>)}
      </div>
      {data && items.length === 0
        ? <EmptyState title={filter === 'active' ? 'Открытых доработок нет' : 'Здесь пусто'} text="Записывайте сюда, что стоит улучшить в проекте." />
        : <Section>
          {items.map(r => (
            <div key={r.id} className={`cell${r.status === 'done' || r.status === 'rejected' ? ' done' : ''}`}>
              <button className={`check${r.status === 'done' ? ' on' : ''}`} aria-label={r.status === 'done' ? 'Вернуть в работу' : 'Отметить сделанной'}
                onClick={() => patch(r.id, { status: r.status === 'done' ? 'open' : 'done' })}>{r.status === 'done' && <Check size={15} strokeWidth={3} />}</button>
              <div className="body">
                <div className="title">{r.text}</div>
                <div className="sub">
                  <span className={r.priority === 'high' ? 'warn' : ''}>{PRIORITY_LABEL[r.priority]}</span>
                  {r.source === 'claude' && <span className="capsule tinted">предложил Claude</span>}
                  <span>{relDate(r.created_at)}</span>
                </div>
              </div>
              <div className="tools">
                <select className="select compact" value={r.status} aria-label="Статус" onChange={e => patch(r.id, { status: e.target.value })}>
                  {(Object.keys(REC_STATUS_LABEL) as RecStatus[]).map(s => <option key={s} value={s}>{REC_STATUS_LABEL[s]}</option>)}
                </select>
                <button className="btn small circle gray" style={{ color: 'var(--red)' }} aria-label="Удалить" title="Удалить" onClick={() => remove(r.id)}><Trash2 size={14} /></button>
              </div>
            </div>
          ))}
        </Section>}
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
    <div className="cols">
      <div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input className="input" style={{ flex: 1 }} placeholder="Что сделано: например, выгрузил свод КТП в Word" value={text}
            onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} />
          <button className="btn filled" style={{ minHeight: 40 }} onClick={add}>Записать</button>
        </div>
        <Section title="Что сделано" foot={activity.length ? undefined : 'Записывайте итоги работы. Позже это будет делать и сам Claude в конце сессии.'}>
          {activity.length > 0 && <ul className="timeline">{activity.map(a => (
            <li key={a.id}>
              <div className="when">{fullDate(a.date)}{a.source === 'claude' ? ', записал Claude' : ''}
                <button className="btn plain" style={{ minHeight: 20, padding: '0 4px' }} aria-label="Удалить запись" onClick={() => remove(a.id)}><X size={13} /></button>
              </div>
              <div>{a.text}</div>
            </li>))}</ul>}
        </Section>
      </div>
      <div>
        <Section title="Стадии">
          <ul className="timeline">
            {[...stages].reverse().map(s => (
              <li key={s.id}>
                <div className="when">{fullDate(s.date)}</div>
                <div>{s.from_stage ? `${STAGE_LABEL[s.from_stage]} → ${STAGE_LABEL[s.to_stage]}` : `Создан: ${STAGE_LABEL[s.to_stage]}`}</div>
                {s.comment && s.comment !== 'Создан' && <div className="muted small-text">{s.comment}</div>}
              </li>))}
          </ul>
        </Section>
        <Section title="Последние коммиты" foot={commits.length ? undefined : 'У папок проекта нет своего git-репозитория.'}>
          {commits.map(c => (
            <div key={c.hash} className="cell">
              <div className="body"><div className="title">{c.subject}</div><div className="sub"><span>{relDate(c.date)}</span><span>{c.hash}</span></div></div>
            </div>))}
        </Section>
      </div>
    </div>
  )
}

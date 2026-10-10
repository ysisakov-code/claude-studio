import { EyeOff, FolderOpen, FolderPlus, Link2, MessageCircle, Plus, Rocket, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import type { Effort, Idea, IdeaStatus, InboxGroup, ProjectCard, ProjectDetail, SessionItem } from '../types'
import { EditableText, EmptyState, Section, Sheet, useAction, useLoad, useToast } from '../ui'
import { EFFORT_LABEL, IDEA_STATUS_LABEL, folderName, nSessions, relDate } from '../util'
import { SessionRow } from './ProjectPage'

/* ---------- идеи ---------- */
export function IdeasPage({ open, onChanged }: { open: (id: number) => void; onChanged: () => void }) {
  const { data, reload } = useLoad(() => Promise.all([api.get<Idea[]>('/api/ideas'), api.get<ProjectCard[]>('/api/projects')]), [])
  const [adding, setAdding] = useState(false)
  const act = useAction()
  const toast = useToast()
  const [ideas, projects] = data ?? [[], []]
  const projectName = (id: number | null) => projects.find(p => p.id === id)?.name

  const patch = async (id: number, body: Record<string, unknown>) => { if (await act(() => api.patch(`/api/ideas/${id}`, body))) reload() }
  const remove = async (id: number) => { await act(() => api.del(`/api/ideas/${id}`), 'Идея удалена'); reload() }
  const start = async (i: Idea) => {
    const p = await act(() => api.post<ProjectDetail>(`/api/ideas/${i.id}/start`, {}), 'Проект создан из идеи')
    if (p) { onChanged(); open(p.id) }
  }
  const active = ideas.filter(i => i.status !== 'started')
  const started = ideas.filter(i => i.status === 'started')

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="large-title">Идеи</h1>
        <span className="spacer" />
        <button className="btn filled circle" aria-label="Новая идея" title="Новая идея" onClick={() => setAdding(true)}><Plus size={20} /></button>
      </div>
      <p className="lede">Задумки будущих проектов и улучшений. Когда решите начать, идея станет проектом на стадии «Проектирую».</p>
      {data && active.length === 0 && (
        <EmptyState title="Запишите первую идею" text="Например: квиз по датам для 9 класса или озвучка постов «Истории зашла»."
          action={<button className="btn filled" onClick={() => setAdding(true)}><Plus size={16} />Новая идея</button>} />
      )}
      <div className="ideas">
        {active.map(i => (
          <article key={i.id} className="idea">
            <EditableText value={i.text} onSave={v => v && patch(i.id, { text: v })} className="input inline-edit t" ariaLabel="Идея" />
            <EditableText value={i.details} onSave={v => patch(i.id, { details: v })} multiline placeholder="Подробности: зачем, для кого, как может выглядеть" ariaLabel="Подробности" />
            <div className="foot">
              <select className="select compact" value={i.effort} aria-label="Объём работы" onChange={e => patch(i.id, { effort: e.target.value })}>
                {(Object.keys(EFFORT_LABEL) as Effort[]).map(k => <option key={k} value={k}>{EFFORT_LABEL[k]} работа</option>)}
              </select>
              <select className="select compact" value={i.status} aria-label="Статус" onChange={e => patch(i.id, { status: e.target.value as IdeaStatus })}>
                {(['idea', 'planned'] as IdeaStatus[]).map(k => <option key={k} value={k}>{IDEA_STATUS_LABEL[k]}</option>)}
              </select>
              {i.related_project_id && <span className="capsule">к проекту «{projectName(i.related_project_id)}»</span>}
            </div>
            <div className="foot">
              <button className="btn filled small" onClick={() => start(i)}><Rocket size={14} />Сделать проектом</button>
              <button className="btn small" onClick={() => toast('Обсуждение с Claude появится на следующем этапе')}><MessageCircle size={14} />Обсудить с Claude</button>
              <button className="btn small circle gray" style={{ marginLeft: 'auto', color: 'var(--red)' }} aria-label="Удалить идею" onClick={() => remove(i.id)}><Trash2 size={14} /></button>
            </div>
          </article>
        ))}
      </div>
      {started.length > 0 && (
        <Section title="Уже стали проектами">
          {started.map(i => (
            <button key={i.id} className="cell button" style={{ width: '100%', border: 0, background: 'none', font: 'inherit', textAlign: 'left' }}
              onClick={() => i.related_project_id && open(i.related_project_id)}>{projectName(i.related_project_id) ?? i.text}</button>
          ))}
        </Section>
      )}
      {adding && <IdeaSheet projects={projects} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); reload() }} />}
    </div>
  )
}

function IdeaSheet({ projects, onClose, onSaved }: { projects: ProjectCard[]; onClose: () => void; onSaved: () => void }) {
  const [text, setText] = useState('')
  const [details, setDetails] = useState('')
  const [effort, setEffort] = useState<Effort>('medium')
  const [related, setRelated] = useState('')
  const [err, setErr] = useState('')
  const act = useAction()
  const submit = async () => {
    if (!text.trim()) { setErr('Опишите идею хотя бы одной фразой'); return }
    if (await act(() => api.post('/api/ideas', { text: text.trim(), details, effort, related_project_id: related ? Number(related) : null }), 'Идея записана')) onSaved()
  }
  return (
    <Sheet title="Новая идея" onClose={onClose} done={submit} doneLabel="Записать">
      <label className="field"><span>Идея</span>
        <input className="input" value={text} onChange={e => { setText(e.target.value); setErr('') }} placeholder="Квиз по датам для 9 класса" />
        {err && <span className="error-text">{err}</span>}
      </label>
      <label className="field"><span>Подробности</span>
        <textarea className="textarea" value={details} onChange={e => setDetails(e.target.value)} placeholder="Зачем, для кого, как может выглядеть" />
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="field"><span>Объём работы</span>
          <select className="select" value={effort} onChange={e => setEffort(e.target.value as Effort)}>
            {(Object.keys(EFFORT_LABEL) as Effort[]).map(k => <option key={k} value={k}>{EFFORT_LABEL[k]}</option>)}
          </select>
        </label>
        <label className="field"><span>Связана с проектом</span>
          <select className="select" value={related} onChange={e => setRelated(e.target.value)}>
            <option value="">Ни с каким</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </div>
    </Sheet>
  )
}

/* ---------- «Разобрать» ---------- */
export function InboxPage({ open, onChanged }: { open: (id: number) => void; onChanged: () => void }) {
  const { data, reload } = useLoad(() => Promise.all([api.get<InboxGroup[]>('/api/inbox'), api.get<ProjectCard[]>('/api/projects')]), [])
  const [attachFor, setAttachFor] = useState<InboxGroup | null>(null)
  const act = useAction()
  const [groups, projects] = data ?? [[], []]
  const done = () => { reload(); onChanged() }

  const create = async (g: InboxGroup) => {
    const p = await act(() => api.post<ProjectDetail>('/api/inbox/create-project', { path: g.path }), `Проект «${folderName(g.path)}» создан`)
    if (p) { onChanged(); open(p.id) }
  }
  const ignore = async (g: InboxGroup) => { if (await act(() => api.post('/api/inbox/ignore', { path: g.path }), 'Папка скрыта') !== undefined) done() }

  return (
    <div className="page">
      <div className="page-head"><h1 className="large-title">Разобрать</h1></div>
      <p className="lede">Папки, где вы работали с Claude Code, но которые ещё не относятся ни к одному проекту. Сделайте папку проектом, добавьте к существующему или скройте, если это не проект.</p>
      {data && groups.length === 0 && <EmptyState title="Всё разобрано" text="Все сессии Claude Code относятся к проектам. Новые папки появятся здесь сами." />}
      {groups.map(g => (
        <section key={g.path_key} className="folder-card">
          <div className="folder-head">
            <div style={{ flex: 1, minWidth: 240 }}>
              <div className="folder-name">{folderName(g.path)}</div>
              <div className="mono-path">{g.path}</div>
              <div className="muted small-text" style={{ marginTop: 2 }}>{nSessions(g.session_count)}, последняя {relDate(g.last_activity)}{g.exists === false ? '. Папки уже нет на диске' : ''}</div>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button className="btn filled small" onClick={() => create(g)}><FolderPlus size={14} />Сделать проектом</button>
              <button className="btn small" onClick={() => setAttachFor(g)} disabled={projects.length === 0}><Link2 size={14} />К проекту</button>
              {g.exists !== false && <button className="btn small circle gray" title="Открыть папку" aria-label="Открыть папку" onClick={() => act(() => api.post('/api/open', { path: g.path }))}><FolderOpen size={14} /></button>}
              <button className="btn small gray" onClick={() => ignore(g)}><EyeOff size={14} />Скрыть</button>
            </div>
          </div>
          <ul>{g.sessions.map(s => <li key={s.id}><span className="when">{relDate(s.ended_at)}</span><span>{s.display_title}</span></li>)}</ul>
        </section>
      ))}
      {attachFor && <AttachSheet group={attachFor} projects={projects} onClose={() => setAttachFor(null)} onDone={() => { setAttachFor(null); done() }} />}
    </div>
  )
}

function AttachSheet({ group, projects, onClose, onDone }: { group: InboxGroup; projects: ProjectCard[]; onClose: () => void; onDone: () => void }) {
  const [pid, setPid] = useState(String(projects[0]?.id ?? ''))
  const act = useAction()
  const submit = async () => {
    const r = await act(() => api.post('/api/inbox/attach', { path: group.path, project_id: Number(pid) }), 'Папка добавлена к проекту')
    if (r) onDone()
  }
  return (
    <Sheet title={`«${folderName(group.path)}» к проекту`} onClose={onClose} done={submit} doneLabel="Добавить">
      <p className="muted" style={{ margin: 0 }}>Все сессии из этой папки и её подпапок будут относиться к выбранному проекту.</p>
      <select className="select" value={pid} onChange={e => setPid(e.target.value)} aria-label="Проект">
        {projects.map(p => <option key={p.id} value={p.id}>{p.parent_name ? `${p.parent_name} › ` : ''}{p.name}</option>)}
      </select>
    </Sheet>
  )
}

/* ---------- все сессии ---------- */
export function SessionsPage({ version }: { version: number }) {
  const { data, reload } = useLoad(() => Promise.all([api.get<SessionItem[]>('/api/sessions'), api.get<ProjectCard[]>('/api/projects')]), [version])
  const [only, setOnly] = useState<'all' | 'free'>('all')
  const [sessions, projects] = data ?? [[], []]
  const shown = only === 'free' ? sessions.filter(s => !s.project_id) : sessions
  return (
    <div className="page">
      <div className="page-head">
        <h1 className="large-title">Сессии</h1>
        <span className="spacer" />
        <div className="segmented" role="group" aria-label="Фильтр">
          <button aria-pressed={only === 'all'} onClick={() => setOnly('all')}>Все</button>
          <button aria-pressed={only === 'free'} onClick={() => setOnly('free')}>Без проекта</button>
        </div>
      </div>
      <p className="lede">Все сессии Claude Code на этом компьютере, новые сверху. Двойной щелчок по названию — переименовать.</p>
      <Section>{shown.map(s => <SessionRow key={s.id} s={s} projects={projects} onChanged={reload} showProject />)}</Section>
    </div>
  )
}

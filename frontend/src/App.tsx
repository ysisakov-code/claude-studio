import { FolderKanban, Inbox, Lightbulb, MessagesSquare, Moon, RefreshCw, Search, Sun, SunMoon, type LucideIcon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { IdeasPage, InboxPage, SessionsPage } from './pages/Other'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/Projects'
import { SearchPalette } from './Search'
import type { InboxGroup, ScanRun } from './types'
import { useAction } from './ui'
import { relDate } from './util'

type PageId = 'projects' | 'ideas' | 'inbox' | 'sessions'
type Route = { page: PageId } | { page: 'project'; id: number }
type Theme = 'system' | 'light' | 'dark'
const THEME_KEY = 'studio.theme'

const NAV: { id: PageId; label: string; icon: LucideIcon; color: string }[] = [
  { id: 'projects', label: 'Проекты', icon: FolderKanban, color: 'var(--blue)' },
  { id: 'ideas', label: 'Идеи', icon: Lightbulb, color: 'var(--orange)' },
  { id: 'sessions', label: 'Сессии', icon: MessagesSquare, color: 'var(--purple)' },
  { id: 'inbox', label: 'Разобрать', icon: Inbox, color: 'var(--red)' },
]

function readTheme(): Theme {
  try { return (localStorage.getItem(THEME_KEY) as Theme) || 'system' } catch { return 'system' }
}

export default function App() {
  const [route, setRoute] = useState<Route>({ page: 'projects' })
  const [version, setVersion] = useState(0)
  const [inboxCount, setInboxCount] = useState(0)
  const [lastScan, setLastScan] = useState<ScanRun | null>(null)
  const [scanning, setScanning] = useState(false)
  const [searching, setSearching] = useState(false)
  const [theme, setTheme] = useState<Theme>(readTheme)
  const act = useAction()

  const changed = useCallback(() => setVersion(v => v + 1), [])

  useEffect(() => {
    api.get<InboxGroup[]>('/api/inbox').then(g => setInboxCount(g.length)).catch(() => {})
    api.get<ScanRun | null>('/api/scan/last').then(setLastScan).catch(() => {})
  }, [version])

  // Скан при запуске идёт в фоне на сервере; через пару секунд подтягиваем свежие данные.
  useEffect(() => {
    const t = setTimeout(changed, 3000)
    return () => clearTimeout(t)
  }, [changed])

  useEffect(() => {
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    }
    apply()
    try { localStorage.setItem(THEME_KEY, theme) } catch { /* нет хранилища */ }
    const mq = matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [theme])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'л')) { e.preventDefault(); setSearching(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const rescan = async () => {
    setScanning(true)
    const r = await act(() => api.post<ScanRun>('/api/scan'))
    setScanning(false)
    if (r) { setLastScan(r); changed() }
  }

  const openProject = (id: number) => { setRoute({ page: 'project', id }); document.querySelector('.main')?.scrollTo(0, 0) }
  const nav = (page: PageId) => setRoute({ page })
  const current: PageId = route.page === 'project' ? 'projects' : route.page
  const nextTheme: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }
  const themeLabel: Record<Theme, string> = { system: 'Как в системе', light: 'Светлая тема', dark: 'Тёмная тема' }
  const ThemeIcon = theme === 'light' ? Sun : theme === 'dark' ? Moon : SunMoon

  return (
    <div className="app">
      <nav className="side" aria-label="Разделы">
        <div className="side-title">Студия</div>
        <button className="searchbar" onClick={() => setSearching(true)}><Search size={16} />Поиск<kbd>Ctrl K</kbd></button>
        {NAV.map(n => (
          <button key={n.id} className="nav-row" aria-current={current === n.id ? 'page' : undefined} onClick={() => nav(n.id)}>
            <span className="icon-tile" style={{ background: n.color }}><n.icon size={16} strokeWidth={2.2} /></span>{n.label}
            {n.id === 'inbox' && inboxCount > 0 && <span className="badge">{inboxCount}</span>}
          </button>
        ))}
        <div className="side-foot">
          <button className="nav-row" onClick={rescan} disabled={scanning}>
            <span className="icon-tile" style={{ background: 'var(--gray)' }}><RefreshCw size={15} className={scanning ? 'spinner' : ''} /></span>
            {scanning ? 'Обновляю…' : 'Обновить'}
          </button>
          <button className="nav-row" onClick={() => setTheme(nextTheme[theme])} title="Сменить тему">
            <span className="icon-tile" style={{ background: 'var(--indigo)' }}><ThemeIcon size={15} /></span>{themeLabel[theme]}
          </button>
          <div className="side-note">{lastScan ? `Сессии прочитаны ${relDate(lastScan.started_at)}` : 'Читаю сессии Claude Code…'}</div>
        </div>
      </nav>

      <main className="main">
        {route.page === 'projects' && <ProjectsPage open={openProject} version={version} />}
        {route.page === 'project' && <ProjectPage key={route.id} id={route.id} back={() => nav('projects')} open={openProject} onChanged={changed} />}
        {route.page === 'ideas' && <IdeasPage open={openProject} onChanged={changed} />}
        {route.page === 'inbox' && <InboxPage open={openProject} onChanged={changed} />}
        {route.page === 'sessions' && <SessionsPage version={version} />}
      </main>

      <nav className="tabbar" aria-label="Разделы">
        {NAV.map(n => (
          <button key={n.id} aria-current={current === n.id ? 'page' : undefined} onClick={() => nav(n.id)}>
            <n.icon size={23} strokeWidth={current === n.id ? 2.4 : 1.8} />{n.label}
            {n.id === 'inbox' && inboxCount > 0 && <span className="badge">{inboxCount}</span>}
          </button>
        ))}
        <button onClick={() => setSearching(true)}><Search size={23} strokeWidth={1.8} />Поиск</button>
      </nav>

      {searching && <SearchPalette onClose={() => setSearching(false)} openProject={openProject} openSessions={() => nav('sessions')} />}
    </div>
  )
}

import { FolderKanban, Inbox, Lightbulb, MessagesSquare, Moon, RefreshCw, Search, Sun, SunMoon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { IdeasPage, InboxPage, SessionsPage } from './pages/Other'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/Projects'
import { SearchPalette } from './Search'
import type { InboxGroup, ScanRun } from './types'
import { useAction } from './ui'
import { relDate } from './util'

type Route = { page: 'projects' | 'ideas' | 'inbox' | 'sessions' } | { page: 'project'; id: number }
type Theme = 'system' | 'light' | 'dark'
const THEME_KEY = 'studio.theme'

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
    if (r) {
      setLastScan(r)
      changed()
      if (r.warnings.length) console.warn('Предупреждения скана', r.warnings)
    }
  }

  const openProject = (id: number) => setRoute({ page: 'project', id })
  const nav = (page: 'projects' | 'ideas' | 'inbox' | 'sessions') => setRoute({ page })
  const current = route.page === 'project' ? 'projects' : route.page
  const nextTheme: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }
  const themeLabel: Record<Theme, string> = { system: 'Тема как в Windows', light: 'Светлая тема', dark: 'Тёмная тема' }
  const ThemeIcon = theme === 'light' ? Sun : theme === 'dark' ? Moon : SunMoon

  return (
    <div className="app">
      <nav className="rail" aria-label="Разделы">
        <div className="brand">Студия<small>проекты с Claude</small></div>
        <button className="nav-item" aria-current={current === 'projects' ? 'page' : undefined} onClick={() => nav('projects')}><FolderKanban size={17} />Проекты</button>
        <button className="nav-item" aria-current={current === 'ideas' ? 'page' : undefined} onClick={() => nav('ideas')}><Lightbulb size={17} />Идеи</button>
        <button className="nav-item" aria-current={current === 'sessions' ? 'page' : undefined} onClick={() => nav('sessions')}><MessagesSquare size={17} />Сессии</button>
        <button className="nav-item" aria-current={current === 'inbox' ? 'page' : undefined} onClick={() => nav('inbox')}>
          <Inbox size={17} />Разобрать{inboxCount > 0 && <span className="count alert">{inboxCount}</span>}
        </button>
        <button className="nav-item" onClick={() => setSearching(true)}><Search size={17} />Поиск<span className="count"><kbd>Ctrl</kbd> <kbd>K</kbd></span></button>

        <div className="rail-foot">
          <button className="nav-item" onClick={rescan} disabled={scanning}>
            <RefreshCw size={17} className={scanning ? 'spinner' : ''} />{scanning ? 'Обновляю…' : 'Обновить'}
          </button>
          <button className="nav-item" onClick={() => setTheme(nextTheme[theme])} title="Сменить тему"><ThemeIcon size={17} />{themeLabel[theme]}</button>
          <div className="rail-note">{lastScan ? `Сессии прочитаны ${relDate(lastScan.started_at)}` : 'Читаю сессии Claude Code…'}</div>
        </div>
      </nav>

      <main className="main">
        {route.page === 'projects' && <ProjectsPage open={openProject} version={version} />}
        {route.page === 'project' && <ProjectPage key={route.id} id={route.id} back={() => nav('projects')} onChanged={changed} />}
        {route.page === 'ideas' && <IdeasPage open={openProject} onChanged={changed} />}
        {route.page === 'inbox' && <InboxPage open={openProject} onChanged={changed} />}
        {route.page === 'sessions' && <SessionsPage version={version} />}
      </main>

      {searching && <SearchPalette onClose={() => setSearching(false)} openProject={openProject} openSessions={() => nav('sessions')} />}
    </div>
  )
}

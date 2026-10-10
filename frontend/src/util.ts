import type { Effort, IdeaStatus, Priority, RecStatus, Stage } from './types'

export const STAGES: { id: Stage; label: string; hint: string }[] = [
  { id: 'idea', label: 'Идея', hint: 'Задумка, ещё не начата' },
  { id: 'design', label: 'Проектирую', hint: 'Продумываю, как сделать' },
  { id: 'build', label: 'Делаю', hint: 'Идёт разработка' },
  { id: 'live', label: 'Работает', hint: 'Проектом пользуются' },
  { id: 'paused', label: 'Пауза', hint: 'Отложен' },
]
export const STAGE_LABEL: Record<Stage, string> = {
  idea: 'Идея', design: 'Проектирую', build: 'Делаю', live: 'Работает', paused: 'Пауза', archived: 'В архиве',
}
export const PRIORITY_LABEL: Record<Priority, string> = { high: 'Важно', normal: 'Обычно', low: 'Не срочно' }
export const REC_STATUS_LABEL: Record<RecStatus, string> = {
  open: 'Открыта', in_progress: 'В работе', done: 'Сделано', rejected: 'Отклонена',
}
export const EFFORT_LABEL: Record<Effort, string> = { small: 'Небольшая', medium: 'Средняя', large: 'Большая' }
export const IDEA_STATUS_LABEL: Record<IdeaStatus, string> = { idea: 'Идея', planned: 'В планах', started: 'Начата' }

const plural = (n: number, one: string, few: string, many: string) => {
  const m10 = n % 10, m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few
  return many
}
export const nDays = (n: number) => `${n} ${plural(n, 'день', 'дня', 'дней')}`
export const nSessions = (n: number) => `${n} ${plural(n, 'сессия', 'сессии', 'сессий')}`
export const nPrompts = (n: number) => `${n} ${plural(n, 'запрос', 'запроса', 'запросов')}`
export const nRecs = (n: number) => `${n} ${plural(n, 'доработка', 'доработки', 'доработок')}`

export function relDate(iso: string | null | undefined): string {
  if (!iso) return 'сессий не было'
  const d = new Date(iso)
  const now = new Date()
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(d)) / 86_400_000)
  const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  if (days === 0) return `сегодня в ${time}`
  if (days === 1) return `вчера в ${time}`
  if (days < 7) return `${nDays(days)} назад`
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' })
}

export function fullDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function duration(a: string | null, b: string | null): string {
  if (!a || !b) return ''
  const min = Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60_000)
  if (min < 1) return 'меньше минуты'
  if (min < 60) return `${min} мин`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} ч ${min % 60} мин`
  return nDays(Math.floor(h / 24))
}

export const folderName = (p: string) => p.split(/[\\/]/).filter(Boolean).pop() ?? p

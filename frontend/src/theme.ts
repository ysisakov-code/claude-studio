// Оформление проекта по смыслу: цвет и значок. Если пользователь выбрал свои — берутся они.
import {
  BookOpen, Bot, Brain, Code2, Film, Gamepad2, Globe, GraduationCap, Landmark, Map, Mic, Music,
  Palette, Presentation, Send, Shield, Sparkles, TrendingUp, type LucideIcon,
} from 'lucide-react'

export const ICONS: Record<string, { icon: LucideIcon; label: string }> = {
  landmark: { icon: Landmark, label: 'История' },
  map: { icon: Map, label: 'Карты' },
  school: { icon: GraduationCap, label: 'Школа' },
  book: { icon: BookOpen, label: 'Книга' },
  game: { icon: Gamepad2, label: 'Игра' },
  send: { icon: Send, label: 'Telegram' },
  bot: { icon: Bot, label: 'Бот' },
  mic: { icon: Mic, label: 'Голос' },
  shield: { icon: Shield, label: 'Защита' },
  trend: { icon: TrendingUp, label: 'Деньги' },
  globe: { icon: Globe, label: 'Сайт' },
  slides: { icon: Presentation, label: 'Презентация' },
  film: { icon: Film, label: 'Видео' },
  music: { icon: Music, label: 'Музыка' },
  brain: { icon: Brain, label: 'ИИ' },
  code: { icon: Code2, label: 'Код' },
  art: { icon: Palette, label: 'Дизайн' },
  spark: { icon: Sparkles, label: 'Другое' },
}

// Цвета близки к системным цветам iOS, но подобраны под смысл: пергамент истории, школьный индиго, игровой фиолет.
export const COLORS: { hex: string; label: string }[] = [
  { hex: '#C47F2C', label: 'Пергамент' },
  { hex: '#D9573B', label: 'Киноварь' },
  { hex: '#FF9500', label: 'Оранжевый' },
  { hex: '#34C759', label: 'Зелёный' },
  { hex: '#30B0C7', label: 'Бирюзовый' },
  { hex: '#229ED9', label: 'Telegram' },
  { hex: '#007AFF', label: 'Синий' },
  { hex: '#5856D6', label: 'Индиго' },
  { hex: '#8E44C9', label: 'Фиолетовый' },
  { hex: '#FF2D55', label: 'Розовый' },
  { hex: '#8E8E93', label: 'Графит' },
]

const RULES: { words: string[]; color: string; icon: string }[] = [
  { words: ['атлас', 'карт', 'map'], color: '#30B0C7', icon: 'map' },
  { words: ['лента', 'сайт', 'тренаж', 'web'], color: '#C47F2C', icon: 'globe' },
  { words: ['истори', 'егэ', 'огэ'], color: '#C47F2C', icon: 'landmark' },
  { words: ['журнал', 'учител', 'школ', 'класс', 'ктп', 'урок'], color: '#5856D6', icon: 'school' },
  { words: ['игр', 'unreal', 'ue5', 'мытарств', 'game'], color: '#8E44C9', icon: 'game' },
  { words: ['telegram', 'телеграм', 'канал', 'контент', 'завод', 'пост'], color: '#229ED9', icon: 'send' },
  { words: ['бот', 'bot'], color: '#229ED9', icon: 'bot' },
  { words: ['джарвис', 'голос', 'ассистент', 'voice'], color: '#FF2D55', icon: 'mic' },
  { words: ['впн', 'vpn', 'прокси', 'защит'], color: '#8E8E93', icon: 'shield' },
  { words: ['капитал', 'деньг', 'робот', 'трейд', 'инвест'], color: '#34C759', icon: 'trend' },
  { words: ['презентац', 'слайд'], color: '#FF9500', icon: 'slides' },
  { words: ['видео', 'youtube', 'tiktok', 'ролик'], color: '#D9573B', icon: 'film' },
]

export interface Themed { name: string; description?: string; tags?: string[]; color?: string | null; icon?: string | null }

export function projectTheme(p: Themed): { color: string; icon: string; Icon: LucideIcon } {
  // Смысл ищем по убыванию надёжности: название, теги, описание.
  const sources = [p.name, (p.tags ?? []).join(' '), p.description ?? ''].map(s => s.toLowerCase())
  let rule: (typeof RULES)[number] | undefined
  for (const hay of sources) {
    rule = RULES.find(r => r.words.some(w => hay.includes(w)))
    if (rule) break
  }
  const color = p.color || rule?.color || '#007AFF'
  const icon = p.icon && ICONS[p.icon] ? p.icon : rule?.icon || 'spark'
  return { color, icon, Icon: ICONS[icon].icon }
}

/** Смешать цвет с белым (amount > 0) или чёрным (amount < 0). */
export function shade(hex: string, amount: number): string {
  const n = parseInt(hex.slice(1), 16)
  const mix = (c: number) => Math.round(amount >= 0 ? c + (255 - c) * amount : c * (1 + amount))
  const r = mix((n >> 16) & 255), g = mix((n >> 8) & 255), b = mix(n & 255)
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`
}

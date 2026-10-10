import type { CSSProperties } from 'react'
import { assetUrl } from './api'
import { projectTheme, shade } from './theme'
import type { ProjectCard } from './types'

/** Обложка проекта: картинка из проекта; у проекта с частями — коллаж их обложек;
 *  иначе оформление по смыслу — градиент цвета темы и значок. */
export function Cover({ p, parts = [], className = '', showIcon = true, dim = false }: {
  p: ProjectCard; parts?: ProjectCard[]; className?: string; showIcon?: boolean; dim?: boolean
}) {
  const t = projectTheme(p)
  const style = { '--tint': t.color } as CSSProperties
  const withImages = parts.filter(x => x.cover)
  let content
  if (p.cover) {
    content = <img src={assetUrl(`/api/projects/${p.id}/cover?v=${p.cover}`)} alt="" loading="lazy" draggable={false} />
  } else if (withImages.length >= 2) {
    const cells = [...parts].sort((a, b) => Number(!!b.cover) - Number(!!a.cover)).slice(0, 4)
    content = (
      <div className="collage">
        {cells.map(c => <div key={c.id}><Art p={c} small /></div>)}
        {cells.length === 3 && <div><Art p={p} small /></div>}
      </div>
    )
  } else {
    content = <Art p={p} />
  }
  return (
    <div className={`cover ${dim ? 'dim' : ''} ${className}`} style={style}>
      {content}
      {(p.cover || withImages.length >= 2) && showIcon && (
        <>
          <div className="scrim" />
          <span className="chip-icon" style={{ background: t.color }}><t.Icon size={17} strokeWidth={2.2} /></span>
        </>
      )}
      {p.children.length > 0 && showIcon && <span className="parts-badge">{p.children.length} {p.children.length === 1 ? 'часть' : p.children.length < 5 ? 'части' : 'частей'}</span>}
    </div>
  )
}

function Art({ p, small }: { p: ProjectCard; small?: boolean }) {
  const t = projectTheme(p)
  if (small && p.cover) {
    return <img src={assetUrl(`/api/projects/${p.id}/cover?v=${p.cover}`)} alt="" loading="lazy" draggable={false} />
  }
  return (
    <div className="art" style={{ background: `linear-gradient(150deg, ${shade(t.color, .28)} 0%, ${t.color} 45%, ${shade(t.color, -.35)} 100%)` }}>
      <div className="pattern" />
      <t.Icon className="symbol" strokeWidth={1.6} style={small ? { width: '42%', height: '42%' } : undefined} />
    </div>
  )
}

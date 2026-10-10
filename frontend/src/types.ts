export type Stage = 'idea' | 'design' | 'build' | 'live' | 'paused' | 'archived'
export type Priority = 'high' | 'normal' | 'low'
export type RecStatus = 'open' | 'in_progress' | 'done' | 'rejected'
export type Effort = 'small' | 'medium' | 'large'
export type IdeaStatus = 'idea' | 'planned' | 'started'

export interface ProjectCard {
  id: number
  name: string
  description: string
  stage: Stage
  progress: number
  priority: Priority
  tags: string[]
  next_step: string
  primary_path: string | null
  last_activity: string | null
  days_inactive: number | null
  is_stale: boolean
  session_count: number
  open_recommendations: number
  agent_counts: { agent: number; skill: number; mcp: number }
  pinned_count: number
  created_at: string
  updated_at: string
  parent_id: number | null
  parent_name: string | null
  children: number[]
  color: string | null
  icon: string | null
  cover: string | null
  cover_is_custom: boolean
}

export interface Agent {
  id?: number
  name: string
  kind: 'agent' | 'skill' | 'mcp'
  scope: 'project' | 'global'
  description: string
  model: string | null
  file_path: string | null
  missing?: boolean
}

export interface Commit { hash: string; date: string; subject: string }

export interface ProjectPathInfo {
  id: number
  path: string
  is_primary: boolean
  exists: boolean | null
  claude_md: { path: string; summary: string; modified_at: string } | null
  git: { branch: string | null; dirty: boolean; toplevel: string; commits: Commit[] } | null
}

export interface Link { title: string; url: string }

export interface ProjectDetail extends ProjectCard {
  thoughts: string
  claude_ai_links: Link[]
  paths: ProjectPathInfo[]
  agents: Agent[]
  pinned_agents: Agent[]
  parts: ProjectCard[]
}

export interface SessionItem {
  id: string
  project_id: number | null
  project_manual: boolean
  project_name?: string | null
  display_title: string
  title: string | null
  user_title: string
  note: string
  first_prompt: string
  last_prompt: string
  started_at: string | null
  ended_at: string | null
  prompt_count: number
  reply_count: number
  git_branch: string | null
  cwd_start: string | null
  cwd_main: string | null
  entrypoint: string | null
  source: 'jsonl' | 'history'
  file_missing: boolean
  can_resume: boolean
}

export interface InboxGroup {
  path: string
  path_key: string
  exists: boolean | null
  session_count: number
  last_activity: string | null
  sessions: SessionItem[]
}

export interface Recommendation {
  id: number
  project_id: number
  text: string
  priority: Priority
  status: RecStatus
  source: 'manual' | 'claude'
  created_at: string
}

export interface Idea {
  id: number
  text: string
  details: string
  related_project_id: number | null
  effort: Effort
  status: IdeaStatus
  created_at: string
}

export interface StageEntry { id: number; from_stage: Stage | null; to_stage: Stage; date: string; comment: string }
export interface ActivityEntry { id: number; date: string; text: string; source: 'manual' | 'claude' }
export interface ScanRun { id: number; started_at: string; duration_s: number; sessions_total: number; sessions_parsed: number; warnings: string[] }

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL
const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Database types
export interface BreachRecord {
  id: number
  organization_name: string
  breach_date: string | null
  reported_date: string | null
  affected_individuals: number | null
  what_was_leaked: string | null
  data_types_compromised: string[] | null
  notice_document_url: string | null
  source_id: number
  source_name: string
  source_type: string
  publication_date: string | null
  summary_text: string | null
  tags_keywords: string[] | null
  incident_nature_text: string | null
  incident_discovery_date: string | null
  is_cybersecurity_related: boolean | null
  item_url: string | null
  created_at: string
  scraped_at: string | null
}

export interface DataSource {
  id: number
  name: string
  url: string | null
  type: string | null
  description: string | null
  created_at: string
}

export interface UserPrefs {
  user_id: string
  threshold: number
  sources: string[]
  source_types: string[]
  data_types: string[]
  keywords: string[]
  created_at: string
  updated_at: string
}

export interface ResearchJob {
  id: string
  scraped_item: string
  status: 'pending' | 'planned' | 'running' | 'done' | 'failed'
  report_url: string | null
  requested_by: string
  created_at: string
  completed_at: string | null
  error_message: string | null
}

// API functions
export async function getBreaches(params: {
  page?: number
  limit?: number
  sourceTypes?: string[]
  minAffected?: number
  search?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
} = {}) {
  const {
    page = 0,
    limit = 50,
    sourceTypes = [],
    minAffected = 0,
    search = '',
    sortBy = 'publication_date',
    sortOrder = 'desc'
  } = params

  let query = supabase
    .from('v_breach_dashboard')
    .select('*', { count: 'exact' })

  // Apply filters
  if (sourceTypes.length > 0) {
    query = query.in('source_type', sourceTypes)
  }

  if (minAffected > 0) {
    query = query.gte('affected_individuals', minAffected)
  }

  if (search) {
    query = query.or(`organization_name.ilike.%${search}%,what_was_leaked.ilike.%${search}%`)
  }

  // Apply sorting
  query = query.order(sortBy, { ascending: sortOrder === 'asc' })

  // Apply pagination
  const from = page * limit
  const to = from + limit - 1
  query = query.range(from, to)

  return query
}

export async function getSourceTypes() {
  const { data, error } = await supabase
    .from('data_sources')
    .select('type')
    .not('type', 'is', null)

  if (error) throw error

  // Get unique source types
  const uniqueTypes = [...new Set(data.map(item => item.type))]
  return uniqueTypes.filter(Boolean)
}

export async function getSourceTypeCounts() {
  const { data, error } = await supabase
    .from('v_breach_dashboard')
    .select('source_type')

  if (error) throw error

  // Count occurrences of each source type
  const counts = data.reduce((acc, item) => {
    const type = item.source_type
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return counts
}

export async function getDataTypes() {
  const { data, error } = await supabase
    .from('scraped_items')
    .select('data_types_compromised')
    .not('data_types_compromised', 'is', null)

  if (error) throw error

  // Flatten and get unique data types
  const allTypes = data.flatMap(item => item.data_types_compromised || [])
  return [...new Set(allTypes)].filter(Boolean)
}

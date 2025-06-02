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
  scrapedDateRange?: string
  breachDateRange?: string
  publicationDateRange?: string
} = {}) {
  const {
    page = 0,
    limit = 50,
    sourceTypes = [],
    minAffected = 0,
    search = '',
    sortBy = 'publication_date',
    sortOrder = 'desc',
    scrapedDateRange = '',
    breachDateRange = '',
    publicationDateRange = ''
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

  // Apply date filters
  if (scrapedDateRange) {
    const dateFilter = parseDateRange(scrapedDateRange)
    if (dateFilter.start) {
      query = query.gte('scraped_at', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('scraped_at', dateFilter.end)
    }
  }

  if (breachDateRange) {
    const dateFilter = parseDateRange(breachDateRange)
    if (dateFilter.start) {
      query = query.gte('breach_date', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('breach_date', dateFilter.end)
    }
  }

  if (publicationDateRange) {
    const dateFilter = parseDateRange(publicationDateRange)
    if (dateFilter.start) {
      query = query.gte('publication_date', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('publication_date', dateFilter.end)
    }
  }

  // Apply sorting
  query = query.order(sortBy, { ascending: sortOrder === 'asc' })

  // Apply pagination
  const from = page * limit
  const to = from + limit - 1
  query = query.range(from, to)

  return query
}

// Helper function to parse date range strings
function parseDateRange(range: string): { start?: string; end?: string } {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  switch (range) {
    case 'today':
      return {
        start: today.toISOString(),
        end: new Date(today.getTime() + 24 * 60 * 60 * 1000).toISOString()
      }

    case 'yesterday':
      const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
      return {
        start: yesterday.toISOString(),
        end: today.toISOString()
      }

    case 'last-3-days':
      return {
        start: new Date(today.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-week':
    case 'last-7-days':
      return {
        start: new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-2-weeks':
      return {
        start: new Date(today.getTime() - 14 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-month':
    case 'last-30-days':
      return {
        start: new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-3-months':
      return {
        start: new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-6-months':
      return {
        start: new Date(today.getTime() - 180 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-year':
      return {
        start: new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'all-time':
      return {}

    default:
      // Handle custom date ranges (format: custom-type-YYYY-MM-DD)
      if (range.startsWith('custom-')) {
        const parts = range.split('-')
        if (parts.length >= 4) {
          const dateStr = parts.slice(2).join('-')
          try {
            const customDate = new Date(dateStr)
            return {
              start: customDate.toISOString(),
              end: new Date(customDate.getTime() + 24 * 60 * 60 * 1000).toISOString()
            }
          } catch {
            return {}
          }
        }
      }
      return {}
  }
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

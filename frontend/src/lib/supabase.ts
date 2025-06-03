import { createClient } from '@supabase/supabase-js'

// Get Supabase configuration from environment variables
const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL || 'https://hilbbjnnxkitxbptektg.supabase.co'
const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpbGJiam5ueGtpdHhicHRla3RnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxOTYwNDIsImV4cCI6MjA2Mzc3MjA0Mn0.vk8AJ2pofRAy5y26WQeMYgEFudU1plXnYa6sMFyATFM'

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing Supabase environment variables')
  console.error('PUBLIC_SUPABASE_URL:', supabaseUrl)
  console.error('PUBLIC_SUPABASE_ANON_KEY:', supabaseAnonKey ? 'Set' : 'Missing')
  throw new Error('Missing Supabase environment variables')
}

console.log('Supabase configuration:', {
  url: supabaseUrl,
  keyLength: supabaseAnonKey.length,
  environment: import.meta.env.MODE
})

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Helper functions to distinguish between news and breach sources
export const isNewsSource = (sourceType: string): boolean => {
  return ['News Feed', 'Company IR'].includes(sourceType)
}

export const isBreachSource = (sourceType: string): boolean => {
  return ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API'].includes(sourceType)
}

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

export interface NewsArticle {
  id: number
  title: string
  source_id: number
  source_name: string
  source_type: string
  publication_date: string | null
  summary_text: string | null
  full_content: string | null
  item_url: string | null
  tags_keywords: string[] | null
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
  selectedSources?: number[]
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
    selectedSources = [],
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

  // Filter to only breach sources (exclude news feeds)
  const breachSourceTypes = ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API']
  query = query.in('source_type', breachSourceTypes)

  // Apply filters
  if (sourceTypes.length > 0) {
    // Map source types to the new categorization for filtering
    const typeMapping: Record<string, string[]> = {
      'State AG Sites': ['State AG', 'State Cybersecurity', 'State Agency'],
      'Government Portals': ['Government Portal'],
      'Specialized Breach Sites': ['Breach Database'],
      'API Services': ['API']
    }

    const mappedTypes: string[] = []
    sourceTypes.forEach(type => {
      if (typeMapping[type]) {
        mappedTypes.push(...typeMapping[type])
      }
    })

    if (mappedTypes.length > 0) {
      // Intersect with breach source types
      const filteredTypes = mappedTypes.filter(type => breachSourceTypes.includes(type))
      if (filteredTypes.length > 0) {
        query = query.in('source_type', filteredTypes)
      }
    }
  }

  // Apply specific source filtering (takes precedence over source types)
  if (selectedSources.length > 0) {
    query = query.in('source_id', selectedSources)
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

// Get news articles (RSS feeds, Company IR, etc.)
export async function getNewsArticles(params: {
  page?: number
  limit?: number
  selectedSources?: number[]
  search?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  scrapedDateRange?: string
  publicationDateRange?: string
} = {}) {
  const {
    page = 0,
    limit = 50,
    selectedSources = [],
    search = '',
    sortBy = 'publication_date',
    sortOrder = 'desc',
    scrapedDateRange = '',
    publicationDateRange = ''
  } = params

  let query = supabase
    .from('v_breach_dashboard')
    .select('id, title as title, source_id, source_name, source_type, publication_date, summary_text, full_content, item_url, tags_keywords, created_at, scraped_at', { count: 'exact' })

  // Filter to only news sources
  const newsSourceTypes = ['News Feed', 'Company IR']
  query = query.in('source_type', newsSourceTypes)

  // Apply specific source filtering
  if (selectedSources.length > 0) {
    query = query.in('source_id', selectedSources)
  }

  if (search) {
    query = query.or(`title.ilike.%${search}%,summary_text.ilike.%${search}%`)
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

  // Map to new categorization and remove API
  const typeMapping: Record<string, string> = {
    'State AG': 'State AG Sites',
    'Government Portal': 'Government Portals',
    'News Feed': 'RSS News Feeds',
    'Breach Database': 'Specialized Breach Sites',
    'Company IR': 'Company IR Sites',
    'State Cybersecurity': 'State AG Sites', // Group with State AG
    'State Agency': 'State AG Sites' // Group with State AG
  }

  const mappedTypes = data
    .map(item => typeMapping[item.type] || item.type)
    .filter(type => type !== 'API') // Remove API category

  const uniqueTypes = [...new Set(mappedTypes)]
  return uniqueTypes.filter(Boolean)
}

// Get sources by category for hierarchical filtering with breach counts
export async function getSourcesByCategory() {
  const { data: sourcesData, error: sourcesError } = await supabase
    .from('data_sources')
    .select('id, name, type')
    .not('type', 'is', null)

  if (sourcesError) throw sourcesError

  // Get breach counts per source
  const { data: breachCounts, error: breachError } = await supabase
    .from('v_breach_dashboard')
    .select('source_id, source_name')

  if (breachError) throw breachError

  // Count breaches per source
  const sourceBreachCounts = breachCounts.reduce((acc, breach) => {
    acc[breach.source_id] = (acc[breach.source_id] || 0) + 1
    return acc
  }, {} as Record<number, number>)

  console.log('📊 Source breach counts:', sourceBreachCounts)

  // Group sources by new categorization
  const categories: Record<string, Array<{id: number, name: string, originalType: string, itemCount: number, itemType: string}>> = {
    'Government Portals': [],
    'State AG Sites': [],
    'RSS News Feeds': [],
    'Specialized Breach Sites': [],
    'Company IR Sites': []
  }

  sourcesData.forEach(source => {
    let category = ''
    let itemType = 'breaches' // Default for breach notification sources

    switch (source.type) {
      case 'State AG':
      case 'State Cybersecurity':
      case 'State Agency':
        category = 'State AG Sites'
        itemType = 'breaches'
        break
      case 'Government Portal':
        category = 'Government Portals'
        itemType = 'breaches'
        break
      case 'News Feed':
        category = 'RSS News Feeds'
        itemType = 'articles'
        break
      case 'Breach Database':
        category = 'Specialized Breach Sites'
        itemType = 'breaches'
        break
      case 'Company IR':
        category = 'Company IR Sites'
        itemType = 'reports'
        break
      default:
        return // Skip API and unknown types
    }

    if (categories[category]) {
      categories[category].push({
        id: source.id,
        name: source.name,
        originalType: source.type,
        itemCount: sourceBreachCounts[source.id] || 0,
        itemType: itemType
      })
    }
  })

  // Sort sources within each category by item count (descending), then by name
  Object.keys(categories).forEach(category => {
    categories[category].sort((a, b) => {
      if (b.itemCount !== a.itemCount) {
        return b.itemCount - a.itemCount // Sort by item count first
      }
      return a.name.localeCompare(b.name) // Then by name
    })
  })

  console.log('📈 Sources by category with breach counts:', categories)

  return categories
}

export async function getSourceTypeCounts() {
  console.log('🔍 getSourceTypeCounts called')

  const { data, error } = await supabase
    .from('v_breach_dashboard')
    .select('source_type')

  if (error) {
    console.error('❌ Supabase error in getSourceTypeCounts:', error)
    throw error
  }

  console.log('📊 Total records fetched:', data?.length || 0)
  console.log('📊 First 5 records:', data?.slice(0, 5))

  if (!data || data.length === 0) {
    console.warn('⚠️ No data returned from v_breach_dashboard')
    return {}
  }

  // Simple count of entries by source type
  const rawCounts = data.reduce((acc, item) => {
    acc[item.source_type] = (acc[item.source_type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  console.log('📊 Raw source type counts:', rawCounts)

  // Map to display categories
  const categoryMapping: Record<string, string> = {
    'State AG': 'State AG Sites',
    'Government Portal': 'Government Portals',
    'News Feed': 'RSS News Feeds',
    'Breach Database': 'Specialized Breach Sites',
    'Company IR': 'Company IR Sites',
    'State Cybersecurity': 'State AG Sites',
    'State Agency': 'State AG Sites'
  }

  // Convert raw counts to category counts
  const categoryCounts: Record<string, number> = {}

  Object.entries(rawCounts).forEach(([sourceType, count]) => {
    const category = categoryMapping[sourceType]
    console.log(`Mapping: ${sourceType} (${count}) -> ${category}`)
    if (category) {
      categoryCounts[category] = (categoryCounts[category] || 0) + count
    }
  })

  console.log('📈 Final category counts:', categoryCounts)

  return categoryCounts
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

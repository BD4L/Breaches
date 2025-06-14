import React, { useState, useEffect } from 'react'
import { supabase, SOURCE_TYPE_CONFIG } from '../../lib/supabase'
import { formatNumber, formatAffectedCount } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface SourceStats {
  source_id: number
  source_name: string
  source_type: string
  total_items: number
  total_breaches: number
  total_news: number
  total_affected: number
  latest_breach: string | null
  latest_scraped: string | null
  avg_affected_per_breach: number
  is_breach_source: boolean
  item_type_label: string // "breaches", "articles", "reports"
}

interface CategoryStats {
  category: string
  total_sources: number
  total_items: number
  total_breaches: number
  total_news: number
  total_affected: number
  sources: SourceStats[]
}

interface SourceSummaryProps {
  onClose: () => void
}

export function SourceSummary({ onClose }: SourceSummaryProps) {
  const [categoryStats, setCategoryStats] = useState<CategoryStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)

  useEffect(() => {
    loadSourceStats()
  }, [])

  const loadSourceStats = async () => {
    try {
      setLoading(true)
      setError(null)

      // Query to get comprehensive source statistics - exclude API sources like other components
      const { data, error: queryError } = await supabase
        .from('v_breach_dashboard')
        .select(`
          source_id,
          source_name,
          source_type,
          affected_individuals,
          breach_date,
          scraped_at,
          publication_date
        `)
        .neq('source_type', 'API') // Exclude API sources

      if (queryError) throw queryError

      // Process the data to create category statistics
      const sourceMap = new Map<number, SourceStats>()

      data.forEach(record => {
        const sourceId = record.source_id

        if (!sourceMap.has(sourceId)) {
          const isBreachSource = SOURCE_TYPE_CONFIG.isBreachSource(record.source_type)

          // Determine item type label based on source type
          let itemTypeLabel = 'items'
          switch (record.source_type) {
            case 'State AG':
            case 'State Cybersecurity':
            case 'State Agency':
            case 'Government Portal':
            case 'Breach Database':
              itemTypeLabel = 'breaches'
              break
            case 'News Feed':
              itemTypeLabel = 'articles'
              break
            case 'Company IR':
              itemTypeLabel = 'reports'
              break
          }

          sourceMap.set(sourceId, {
            source_id: sourceId,
            source_name: record.source_name,
            source_type: record.source_type,
            total_items: 0,
            total_breaches: 0,
            total_news: 0,
            total_affected: 0,
            latest_breach: null,
            latest_scraped: null,
            avg_affected_per_breach: 0,
            is_breach_source: isBreachSource,
            item_type_label: itemTypeLabel
          })
        }

        const sourceStats = sourceMap.get(sourceId)!

        // Count items based on source type using centralized config
        const isBreachSource = SOURCE_TYPE_CONFIG.isBreachSource(record.source_type)
        const isNewsSource = SOURCE_TYPE_CONFIG.isNewsSource(record.source_type)

        // Increment total items
        sourceStats.total_items++

        // Increment appropriate category count
        if (isBreachSource) {
          sourceStats.total_breaches++
        } else if (isNewsSource) {
          sourceStats.total_news++
        }

        // Only count affected individuals for breach sources
        if (isBreachSource && record.affected_individuals) {
          sourceStats.total_affected += record.affected_individuals
        }

        // Update latest dates
        if (record.breach_date && (!sourceStats.latest_breach || record.breach_date > sourceStats.latest_breach)) {
          sourceStats.latest_breach = record.breach_date
        }

        if (record.scraped_at && (!sourceStats.latest_scraped || record.scraped_at > sourceStats.latest_scraped)) {
          sourceStats.latest_scraped = record.scraped_at
        }
      })

      // Calculate averages and group by category
      const categoryMap = new Map<string, CategoryStats>()

      sourceMap.forEach(sourceStats => {
        // Only calculate averages for breach sources with breaches
        if (sourceStats.is_breach_source && sourceStats.total_breaches > 0) {
          sourceStats.avg_affected_per_breach = sourceStats.total_affected / sourceStats.total_breaches
        } else {
          sourceStats.avg_affected_per_breach = 0
        }

        const category = SOURCE_TYPE_CONFIG.getDisplayCategory(sourceStats.source_type)

        if (!categoryMap.has(category)) {
          categoryMap.set(category, {
            category,
            total_sources: 0,
            total_items: 0,
            total_breaches: 0,
            total_news: 0,
            total_affected: 0,
            sources: []
          })
        }

        const categoryStats = categoryMap.get(category)!
        categoryStats.total_sources++
        categoryStats.total_items += sourceStats.total_items
        categoryStats.total_breaches += sourceStats.total_breaches
        categoryStats.total_news += sourceStats.total_news
        categoryStats.total_affected += sourceStats.total_affected
        categoryStats.sources.push(sourceStats)
      })

      // Sort sources within each category by total items (breaches + news)
      categoryMap.forEach(category => {
        category.sources.sort((a, b) => b.total_items - a.total_items)
      })

      // Convert to array and sort by total items
      const categories = Array.from(categoryMap.values())
        .sort((a, b) => b.total_items - a.total_items)

      setCategoryStats(categories)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load source statistics')
    } finally {
      setLoading(false)
    }
  }

  // Category display functions updated to match centralized config
  const getCategoryIcon = (category: string): string => {
    switch (category) {
      case 'State AG Sites': return '🏛️'
      case 'Government Portals': return '🏢'
      case 'RSS News Feeds': return '📰'
      case 'Specialized Breach Sites': return '🔍'
      case 'Company IR Sites': return '💼'
      default: return '📊'
    }
  }

  const getCategoryColor = (category: string): string => {
    switch (category) {
      case 'State AG Sites': return 'bg-blue-100 text-blue-800'
      case 'Government Portals': return 'bg-green-100 text-green-800'
      case 'RSS News Feeds': return 'bg-orange-100 text-orange-800'
      case 'Specialized Breach Sites': return 'bg-purple-100 text-purple-800'
      case 'Company IR Sites': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }



  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4">
          <div className="text-center">
            <h2 className="text-xl font-bold text-red-600 dark:text-red-400 mb-2">
              Error Loading Source Statistics
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">{error}</p>
            <div className="flex space-x-3 justify-center">
              <Button onClick={loadSourceStats}>Try Again</Button>
              <Button variant="outline" onClick={onClose}>Close</Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-7xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              📊 Source Summary Dashboard
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Comprehensive statistics across all breach data sources
            </p>
          </div>
          <Button variant="outline" onClick={onClose}>
            ✕ Close
          </Button>
        </div>

        {/* Overall Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {categoryStats.reduce((sum, cat) => sum + cat.total_sources, 0)}
            </div>
            <div className="text-sm text-blue-800 dark:text-blue-300">Total Sources</div>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formatNumber(categoryStats.reduce((sum, cat) => sum + cat.total_breaches, 0))}
            </div>
            <div className="text-sm text-green-800 dark:text-green-300">Total Breaches</div>
          </div>
          <div className="bg-orange-50 dark:bg-orange-900/20 p-4 rounded-lg">
            <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
              {formatNumber(categoryStats.reduce((sum, cat) => sum + cat.total_news, 0))}
            </div>
            <div className="text-sm text-orange-800 dark:text-orange-300">News Articles</div>
          </div>
          <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {formatAffectedCount(categoryStats.reduce((sum, cat) => sum + cat.total_affected, 0))}
            </div>
            <div className="text-sm text-red-800 dark:text-red-300">People Affected</div>
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Source Categories
          </h3>
          
          {categoryStats.map(category => (
            <div key={category.category} className="border border-gray-200 dark:border-gray-700 rounded-lg">
              <div 
                className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
                onClick={() => setExpandedCategory(
                  expandedCategory === category.category ? null : category.category
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{getCategoryIcon(category.category)}</span>
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-white">
                        {category.category}
                      </h4>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {category.total_sources} sources • {formatNumber(category.total_breaches)} breaches • {formatAffectedCount(category.total_affected)} affected
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Badge className={getCategoryColor(category.category)}>
                      {formatNumber(category.total_breaches)} breaches
                    </Badge>
                    <span className="text-gray-400">
                      {expandedCategory === category.category ? '▼' : '▶'}
                    </span>
                  </div>
                </div>
              </div>

              {expandedCategory === category.category && (
                <div className="border-t border-gray-200 dark:border-gray-700 p-4">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {category.sources.map(source => (
                      <div key={source.source_id} className="bg-gray-50 dark:bg-gray-700 p-3 rounded">
                        <div className="flex justify-between items-start mb-2">
                          <h5 className="font-medium text-gray-900 dark:text-white text-sm">
                            {source.source_name}
                          </h5>
                          <Badge variant="secondary" className="text-xs">
                            ID: {source.source_id}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-400">
                          <div>
                            <span className="font-medium">{source.item_type_label}:</span> {formatNumber(source.is_breach_source ? source.total_breaches : source.total_news)}
                          </div>
                          {source.is_breach_source && (
                            <div>
                              <span className="font-medium">Affected:</span> {formatAffectedCount(source.total_affected)}
                            </div>
                          )}
                          {source.is_breach_source && source.total_breaches > 0 && (
                            <div>
                              <span className="font-medium">Avg/Breach:</span> {formatAffectedCount(Math.round(source.avg_affected_per_breach))}
                            </div>
                          )}
                          <div>
                            <span className="font-medium">Last Scraped:</span> {
                              source.latest_scraped
                                ? new Date(source.latest_scraped).toLocaleDateString()
                                : 'Never'
                            }
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

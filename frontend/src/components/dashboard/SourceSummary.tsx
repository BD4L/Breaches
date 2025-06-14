import React, { useState, useEffect } from 'react'
import { supabase } from '../../lib/supabase'
import { formatNumber, formatAffectedCount, getSourceTypeColor } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface SourceStats {
  source_id: number
  source_name: string
  source_type: string
  total_breaches: number
  total_affected: number
  latest_breach: string | null
  latest_scraped: string | null
  avg_affected_per_breach: number
}

interface CategoryStats {
  category: string
  total_sources: number
  total_breaches: number
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

      // Query to get comprehensive source statistics - match hero section logic
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

      if (queryError) throw queryError

      // Process the data to create category statistics
      const sourceMap = new Map<number, SourceStats>()

      data.forEach(record => {
        const sourceId = record.source_id

        if (!sourceMap.has(sourceId)) {
          sourceMap.set(sourceId, {
            source_id: sourceId,
            source_name: record.source_name,
            source_type: record.source_type,
            total_breaches: 0,
            total_affected: 0,
            latest_breach: null,
            latest_scraped: null,
            avg_affected_per_breach: 0
          })
        }

        const sourceStats = sourceMap.get(sourceId)!

        // Count items based on source type (match hero section logic)
        const isBreachSource = ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API'].includes(record.source_type)
        const isNewsSource = ['News Feed', 'Company IR'].includes(record.source_type)

        if (isBreachSource || isNewsSource) {
          sourceStats.total_breaches++
        }

        if (record.affected_individuals) {
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
        sourceStats.avg_affected_per_breach = sourceStats.total_affected / sourceStats.total_breaches

        const category = mapSourceTypeToCategory(sourceStats.source_type)
        
        if (!categoryMap.has(category)) {
          categoryMap.set(category, {
            category,
            total_sources: 0,
            total_breaches: 0,
            total_affected: 0,
            sources: []
          })
        }

        const categoryStats = categoryMap.get(category)!
        categoryStats.total_sources++
        categoryStats.total_breaches += sourceStats.total_breaches
        categoryStats.total_affected += sourceStats.total_affected
        categoryStats.sources.push(sourceStats)
      })

      // Sort sources within each category by total breaches
      categoryMap.forEach(category => {
        category.sources.sort((a, b) => b.total_breaches - a.total_breaches)
      })

      // Convert to array and sort by total breaches
      const categories = Array.from(categoryMap.values())
        .sort((a, b) => b.total_breaches - a.total_breaches)

      setCategoryStats(categories)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load source statistics')
    } finally {
      setLoading(false)
    }
  }

  const mapSourceTypeToCategory = (sourceType: string): string => {
    // Map the current source types to match hero section categorization
    switch (sourceType) {
      case 'State AG':
      case 'State Cybersecurity':
      case 'State Agency':
        return 'State Attorney General Portals'
      case 'Government Portal':
        return 'Government Portals'
      case 'News Feed':
        return 'RSS News Feeds'
      case 'Breach Database':
        return 'Specialized Breach Sites'
      case 'Company IR':
        return 'Company Investor Relations'
      case 'API':
        return 'API Services'
      default:
        return 'Other Sources'
    }
  }

  const getCategoryIcon = (category: string): string => {
    switch (category) {
      case 'State Attorney General Portals': return '🏛️'
      case 'Government Portals': return '🏢'
      case 'RSS News Feeds': return '📰'
      case 'Specialized Breach Sites': return '🔍'
      case 'Company Investor Relations': return '💼'
      case 'API Services': return '🔌'
      default: return '📊'
    }
  }

  const getCategoryColor = (category: string): string => {
    switch (category) {
      case 'State Attorney General Portals': return 'bg-blue-100 text-blue-800'
      case 'Government Portals': return 'bg-green-100 text-green-800'
      case 'RSS News Feeds': return 'bg-orange-100 text-orange-800'
      case 'Specialized Breach Sites': return 'bg-purple-100 text-purple-800'
      case 'Company Investor Relations': return 'bg-gray-100 text-gray-800'
      case 'API Services': return 'bg-indigo-100 text-indigo-800'
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
          <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {formatAffectedCount(categoryStats.reduce((sum, cat) => sum + cat.total_affected, 0))}
            </div>
            <div className="text-sm text-red-800 dark:text-red-300">People Affected</div>
          </div>
          <div className="bg-purple-50 dark:bg-purple-900/20 p-4 rounded-lg">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {categoryStats.length}
            </div>
            <div className="text-sm text-purple-800 dark:text-purple-300">Categories</div>
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
                            <span className="font-medium">Breaches:</span> {formatNumber(source.total_breaches)}
                          </div>
                          <div>
                            <span className="font-medium">Affected:</span> {formatAffectedCount(source.total_affected)}
                          </div>
                          <div>
                            <span className="font-medium">Avg/Breach:</span> {formatAffectedCount(Math.round(source.avg_affected_per_breach))}
                          </div>
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

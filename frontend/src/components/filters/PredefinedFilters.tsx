import React, { useState, useEffect } from 'react'
import { supabase } from '../../lib/supabase'
import { Clock, TrendingUp, AlertTriangle, Calendar, Building, Zap } from 'lucide-react'

interface PredefinedFilter {
  id: string
  label: string
  description: string
  icon: React.ComponentType<any>
  color: string
  query: {
    search?: string
    sourceTypes?: string[]
    selectedSources?: number[]
    minAffected?: number
    scrapedDateRange?: string
    breachDateRange?: string
    publicationDateRange?: string
  }
  count?: number
}

interface PredefinedFiltersProps {
  onFilterSelect: (filter: PredefinedFilter) => void
  currentView: 'breaches' | 'news' | 'saved'
}

export function PredefinedFilters({ onFilterSelect, currentView }: PredefinedFiltersProps) {
  const [filters, setFilters] = useState<PredefinedFilter[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPredefinedFilters()
  }, [currentView])

  const loadPredefinedFilters = async () => {
    try {
      setLoading(true)
      
      const today = new Date()
      const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
      const yesterdayStart = new Date(todayStart.getTime() - 24 * 60 * 60 * 1000)
      const weekAgo = new Date(todayStart.getTime() - 7 * 24 * 60 * 60 * 1000)
      const monthAgo = new Date(todayStart.getTime() - 30 * 24 * 60 * 60 * 1000)

      // Get counts for each filter
      const [
        todayCount,
        yesterdayCount,
        weekCount,
        stateAGTodayCount,
        highImpactCount,
        recentHighImpactCount
      ] = await Promise.all([
        // Today's breaches
        supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .gte('scraped_at', todayStart.toISOString())
          .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency']),
        
        // Yesterday's breaches
        supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .gte('scraped_at', yesterdayStart.toISOString())
          .lt('scraped_at', todayStart.toISOString())
          .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency']),
        
        // This week's breaches
        supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .gte('scraped_at', weekAgo.toISOString())
          .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency']),
        
        // State AG changes today
        supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .gte('scraped_at', todayStart.toISOString())
          .in('source_type', ['State AG', 'State Cybersecurity', 'State Agency']),
        
        // High impact breaches (>10K affected)
        supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .gte('affected_individuals', 10000)
          .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency']),
        
        // Recent high impact (last 30 days, >5K affected)
        supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .gte('scraped_at', monthAgo.toISOString())
          .gte('affected_individuals', 5000)
          .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency'])
      ])

      const predefinedFilters: PredefinedFilter[] = [
        {
          id: 'today',
          label: 'Today\'s Discoveries',
          description: 'Breaches discovered in the last 24 hours',
          icon: Clock,
          color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800',
          count: todayCount.count || 0,
          query: {
            scrapedDateRange: 'today'
          }
        },
        {
          id: 'yesterday',
          label: 'Yesterday\'s Changes',
          description: 'Compare with previous day discoveries',
          icon: TrendingUp,
          color: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800',
          count: yesterdayCount.count || 0,
          query: {
            scrapedDateRange: 'yesterday'
          }
        },
        {
          id: 'state-ag-today',
          label: 'State AG Updates',
          description: 'New notifications from State Attorney General offices',
          icon: Building,
          color: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
          count: stateAGTodayCount.count || 0,
          query: {
            sourceTypes: ['State AG Sites'],
            scrapedDateRange: 'today'
          }
        },
        {
          id: 'this-week',
          label: 'This Week',
          description: 'All breaches discovered in the last 7 days',
          icon: Calendar,
          color: 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
          count: weekCount.count || 0,
          query: {
            scrapedDateRange: 'last-week'
          }
        },
        {
          id: 'high-impact',
          label: 'High Impact',
          description: 'Breaches affecting 10,000+ individuals',
          icon: AlertTriangle,
          color: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
          count: highImpactCount.count || 0,
          query: {
            minAffected: 10000
          }
        },
        {
          id: 'recent-critical',
          label: 'Recent Critical',
          description: 'High-impact breaches from the last 30 days',
          icon: Zap,
          color: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800',
          count: recentHighImpactCount.count || 0,
          query: {
            minAffected: 5000,
            scrapedDateRange: 'last-month'
          }
        }
      ]

      setFilters(predefinedFilters)
    } catch (error) {
      console.error('Failed to load predefined filters:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Quick Filters</h3>
        <div className="grid grid-cols-2 gap-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="animate-pulse bg-gray-200 dark:bg-gray-700 rounded-lg h-16"></div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Quick Filters</h3>
      <div className="grid grid-cols-2 gap-2">
        {filters.map((filter) => {
          const IconComponent = filter.icon
          return (
            <button
              key={filter.id}
              onClick={() => onFilterSelect(filter)}
              className={`${filter.color} rounded-lg p-3 border transition-all duration-200 hover:scale-105 hover:shadow-md text-left group`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-1">
                    <IconComponent className="w-4 h-4 flex-shrink-0" />
                    <span className="text-sm font-medium truncate">{filter.label}</span>
                  </div>
                  <p className="text-xs opacity-75 line-clamp-2">{filter.description}</p>
                </div>
                <div className="ml-2 flex-shrink-0">
                  <span className="text-lg font-bold">{filter.count}</span>
                </div>
              </div>
            </button>
          )
        })}
      </div>
      
      {/* Additional Quick Actions */}
      <div className="border-t border-gray-200 dark:border-gray-600 pt-3">
        <h4 className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">Data Type Filters</h4>
        <div className="flex flex-wrap gap-1">
          {[
            { label: 'SSN', search: 'social security' },
            { label: 'Medical', search: 'medical OR health OR PHI' },
            { label: 'Financial', search: 'credit card OR financial OR banking' },
            { label: 'Ransomware', search: 'ransomware OR encryption OR locked' },
            { label: 'Email', search: 'email OR phishing' }
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => onFilterSelect({
                id: `data-${item.label.toLowerCase()}`,
                label: `${item.label} Data`,
                description: `Breaches involving ${item.label.toLowerCase()} data`,
                icon: AlertTriangle,
                color: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300',
                query: { search: item.search }
              })}
              className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded text-xs hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
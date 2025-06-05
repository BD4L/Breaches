import React, { useState, useEffect } from 'react'
import { supabase } from '../../lib/supabase'
import { formatNumber, formatAffectedCount } from '../../lib/utils'

interface OverallStats {
  totalSources: number
  totalBreaches: number
  totalAffected: number
  totalNews: number
  lastUpdated: string
}

export function SourceSummaryHero() {
  const [stats, setStats] = useState<OverallStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      setLoading(true)

      // Get breach count (excluding news feeds)
      const { count: totalBreaches } = await supabase
        .from('v_breach_dashboard')
        .select('*', { count: 'exact', head: true })
        .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API'])

      // Get news count
      const { count: totalNews } = await supabase
        .from('v_breach_dashboard')
        .select('*', { count: 'exact', head: true })
        .in('source_type', ['News Feed', 'Company IR'])

      // Get total affected individuals
      const { data: affectedData } = await supabase
        .from('v_breach_dashboard')
        .select('affected_individuals')
        .not('affected_individuals', 'is', null)

      const totalAffected = affectedData?.reduce((sum, item) => sum + (item.affected_individuals || 0), 0) || 0

      // Get source count
      const { data: sourcesData } = await supabase
        .from('data_sources')
        .select('id')

      // Get latest scraped date
      const { data: latestData } = await supabase
        .from('v_breach_dashboard')
        .select('scraped_at')
        .not('scraped_at', 'is', null)
        .order('scraped_at', { ascending: false })
        .limit(1)

      const lastUpdated = latestData?.[0]?.scraped_at || new Date().toISOString()

      setStats({
        totalSources: sourcesData?.length || 0,
        totalBreaches: totalBreaches || 0,
        totalAffected,
        totalNews: totalNews || 0,
        lastUpdated
      })
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="mb-12">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center space-x-3 mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl flex items-center justify-center shadow-xl shadow-blue-500/25">
              <span className="text-white text-2xl">🛡️</span>
            </div>
            <div className="text-left">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 dark:from-white dark:via-blue-100 dark:to-indigo-100 bg-clip-text text-transparent">
                Security Intelligence Hub
              </h1>
              <p className="text-lg text-gray-600 dark:text-gray-400 font-medium">
                Real-time breach monitoring across multiple sources
              </p>
            </div>
          </div>
          <p className="text-gray-600 dark:text-gray-400 max-w-3xl mx-auto leading-relaxed">
            Comprehensive monitoring of security incidents from government portals, state attorney general offices,
            cybersecurity news feeds, and specialized breach databases with AI-powered analysis.
          </p>
        </div>

        {/* Loading Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 p-6 rounded-2xl border border-gray-200 dark:border-gray-700">
              <div className="animate-pulse">
                <div className="w-12 h-12 bg-gray-300 dark:bg-gray-600 rounded-2xl mb-4"></div>
                <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-3/4 mb-2"></div>
                <div className="h-8 bg-gray-300 dark:bg-gray-600 rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-gray-300 dark:bg-gray-600 rounded w-2/3"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="mb-12">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center space-x-3 mb-4">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl flex items-center justify-center shadow-xl shadow-blue-500/25">
            <span className="text-white text-2xl">🛡️</span>
          </div>
          <div className="text-left">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 dark:from-white dark:via-blue-100 dark:to-indigo-100 bg-clip-text text-transparent">
              Security Intelligence Hub
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-400 font-medium">
              Real-time breach monitoring across {stats?.totalSources}+ sources
            </p>
          </div>
        </div>
        <p className="text-gray-600 dark:text-gray-400 max-w-3xl mx-auto leading-relaxed">
          Comprehensive monitoring of security incidents from government portals, state attorney general offices,
          cybersecurity news feeds, and specialized breach databases with AI-powered analysis.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="group relative overflow-hidden bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/20 dark:to-indigo-900/20 p-6 rounded-2xl border border-blue-200/50 dark:border-blue-800/50 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-indigo-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/25">
                <span className="text-white text-xl">📊</span>
              </div>
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">Breach Notifications</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {formatNumber(stats?.totalBreaches || 0)}
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                + {formatNumber(stats?.totalNews || 0)} news articles
              </p>
            </div>
          </div>
        </div>

        <div className="group relative overflow-hidden bg-gradient-to-br from-red-50 to-pink-100 dark:from-red-900/20 dark:to-pink-900/20 p-6 rounded-2xl border border-red-200/50 dark:border-red-800/50 hover:shadow-xl hover:shadow-red-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-red-600 rounded-2xl flex items-center justify-center shadow-lg shadow-red-500/25">
                <span className="text-white text-xl">👥</span>
              </div>
              <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide">People Affected</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {formatAffectedCount(stats?.totalAffected || 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="group relative overflow-hidden bg-gradient-to-br from-green-50 to-emerald-100 dark:from-green-900/20 dark:to-emerald-900/20 p-6 rounded-2xl border border-green-200/50 dark:border-green-800/50 hover:shadow-xl hover:shadow-green-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center shadow-lg shadow-green-500/25">
                <span className="text-white text-xl">🔄</span>
              </div>
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-green-600 dark:text-green-400 uppercase tracking-wide">Active Sources</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{stats?.totalSources}+</p>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Government & News</p>
            </div>
          </div>
        </div>

        <div className="group relative overflow-hidden bg-gradient-to-br from-orange-50 to-amber-100 dark:from-orange-900/20 dark:to-amber-900/20 p-6 rounded-2xl border border-orange-200/50 dark:border-orange-800/50 hover:shadow-xl hover:shadow-orange-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-amber-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/25">
                <span className="text-white text-xl">📅</span>
              </div>
              <div className="w-2 h-2 bg-orange-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-orange-600 dark:text-orange-400 uppercase tracking-wide">Last Updated</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {stats?.lastUpdated ? new Date(stats.lastUpdated).toLocaleDateString() : 'Today'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

import React, { useState, useEffect } from 'react'
import { supabase } from '../../lib/supabase'
import { formatNumber, formatAffectedCount } from '../../lib/utils'
import { TrendingUp, Users, Database, Clock, AlertTriangle } from 'lucide-react'

interface OverallStats {
  totalSources: number
  totalBreaches: number
  totalAffected: number
  totalNews: number
  lastUpdated: string
  todayBreaches: number
  yesterdayBreaches: number
  stateAGSources: number
  governmentPortals: number
  specializedSites: number
  newsFeeds: number
  companyIR: number
}

export function SourceSummaryHero() {
  const [stats, setStats] = useState<OverallStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
    // Refresh every 5 minutes
    const interval = setInterval(loadStats, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const loadStats = async () => {
    try {
      setLoading(true)

      const today = new Date()
      const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
      const yesterdayStart = new Date(todayStart.getTime() - 24 * 60 * 60 * 1000)

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

      // Get today's breaches
      const { count: todayBreaches } = await supabase
        .from('v_breach_dashboard')
        .select('*', { count: 'exact', head: true })
        .gte('scraped_at', todayStart.toISOString())
        .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency'])

      // Get yesterday's breaches for comparison
      const { count: yesterdayBreaches } = await supabase
        .from('v_breach_dashboard')
        .select('*', { count: 'exact', head: true })
        .gte('scraped_at', yesterdayStart.toISOString())
        .lt('scraped_at', todayStart.toISOString())
        .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency'])

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

      // Get updated source type counts
      const { data: sourceTypeData } = await supabase
        .from('v_breach_dashboard')
        .select('source_type')

      const sourceTypeCounts = sourceTypeData?.reduce((acc, item) => {
        acc[item.source_type] = (acc[item.source_type] || 0) + 1
        return acc
      }, {} as Record<string, number>) || {}

      // Map to display categories with updated counts
      const stateAGSources = (sourceTypeCounts['State AG'] || 0) + 
                            (sourceTypeCounts['State Cybersecurity'] || 0) + 
                            (sourceTypeCounts['State Agency'] || 0)
      const governmentPortals = sourceTypeCounts['Government Portal'] || 0
      const specializedSites = sourceTypeCounts['Breach Database'] || 0
      const newsFeeds = sourceTypeCounts['News Feed'] || 0
      const companyIR = sourceTypeCounts['Company IR'] || 0

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
        lastUpdated,
        todayBreaches: todayBreaches || 0,
        yesterdayBreaches: yesterdayBreaches || 0,
        stateAGSources,
        governmentPortals,
        specializedSites,
        newsFeeds,
        companyIR
      })
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl shadow-lg p-8 text-white mb-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-white/20 rounded w-1/3"></div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-6 bg-white/20 rounded"></div>
                <div className="h-8 bg-white/20 rounded"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!stats) return null

  const changeFromYesterday = stats.todayBreaches - stats.yesterdayBreaches
  const changePercentage = stats.yesterdayBreaches > 0 
    ? ((changeFromYesterday / stats.yesterdayBreaches) * 100).toFixed(1)
    : '0'

  return (
    <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl shadow-lg p-8 text-white mb-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">Breach Intelligence Dashboard</h1>
          <p className="text-blue-100">
            Real-time monitoring of data breaches and security incidents
          </p>
        </div>
        <div className="text-right text-blue-100">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Last updated: {new Date(stats.lastUpdated).toLocaleTimeString()}</span>
          </div>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-6">
        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <div className="flex items-center justify-between mb-2">
            <Database className="w-6 h-6 text-blue-200" />
            <span className="text-xs text-blue-200">Total</span>
          </div>
          <div className="text-2xl font-bold">{formatNumber(stats.totalBreaches)}</div>
          <div className="text-sm text-blue-200">Breach Records</div>
        </div>

        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <div className="flex items-center justify-between mb-2">
            <Users className="w-6 h-6 text-red-200" />
            <span className="text-xs text-red-200">Affected</span>
          </div>
          <div className="text-2xl font-bold">{formatAffectedCount(stats.totalAffected)}</div>
          <div className="text-sm text-red-200">People Impacted</div>
        </div>

        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <div className="flex items-center justify-between mb-2">
            <TrendingUp className="w-6 h-6 text-green-200" />
            <span className="text-xs text-green-200">Today</span>
          </div>
          <div className="text-2xl font-bold">{formatNumber(stats.todayBreaches)}</div>
          <div className="text-sm text-green-200 flex items-center">
            New Discoveries
            {changeFromYesterday !== 0 && (
              <span className={`ml-2 text-xs px-2 py-1 rounded-full ${
                changeFromYesterday > 0 
                  ? 'bg-yellow-500/20 text-yellow-200' 
                  : 'bg-green-500/20 text-green-200'
              }`}>
                {changeFromYesterday > 0 ? '+' : ''}{changeFromYesterday} ({changePercentage}%)
              </span>
            )}
          </div>
        </div>

        <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
          <div className="flex items-center justify-between mb-2">
            <AlertTriangle className="w-6 h-6 text-yellow-200" />
            <span className="text-xs text-yellow-200">Sources</span>
          </div>
          <div className="text-2xl font-bold">{formatNumber(stats.totalSources)}</div>
          <div className="text-sm text-yellow-200">Active Monitors</div>
        </div>
      </div>

      {/* Source Type Breakdown */}
      <div className="bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10">
        <h3 className="text-lg font-semibold mb-4 text-white">Source Categories (Live Counts)</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center">
            <div className="text-xl font-bold text-purple-200">{formatNumber(stats.stateAGSources)}</div>
            <div className="text-xs text-purple-300">State AG Sites</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-blue-200">{formatNumber(stats.governmentPortals)}</div>
            <div className="text-xs text-blue-300">Government Portals</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-green-200">{formatNumber(stats.specializedSites)}</div>
            <div className="text-xs text-green-300">Specialized Sites</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-orange-200">{formatNumber(stats.newsFeeds)}</div>
            <div className="text-xs text-orange-300">RSS News Feeds</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-pink-200">{formatNumber(stats.companyIR)}</div>
            <div className="text-xs text-pink-300">Company IR Sites</div>
          </div>
        </div>
      </div>
    </div>
  )
}

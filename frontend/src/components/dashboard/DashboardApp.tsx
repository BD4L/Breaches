import React, { useState, useCallback, useEffect } from 'react'
import { FilterPanel } from '../filters/FilterPanel'
import { DateFilter } from '../filters/DateFilter'
import { BreachTable } from './BreachTable'
import { NewsTable } from '../news/NewsTable'
import { ViewToggle, type ViewType } from './ViewToggle'
import { ScraperControl } from './ScraperControl'
import { SourceSummary } from './SourceSummary'
import { NonWorkingSites } from './NonWorkingSites'
import { Button } from '../ui/Button'
import { supabase, isNewsSource, isBreachSource } from '../../lib/supabase'

interface Filters {
  search: string
  sourceTypes: string[]
  selectedSources: number[]
  minAffected: number
  scrapedDateRange: string
  breachDateRange: string
  publicationDateRange: string
}

export function DashboardApp() {
  const [currentView, setCurrentView] = useState<ViewType>('breaches')
  const [breachCount, setBreachCount] = useState<number | undefined>(undefined)
  const [newsCount, setNewsCount] = useState<number | undefined>(undefined)
  const [filters, setFilters] = useState<Filters>({
    search: '',
    sourceTypes: [],
    selectedSources: [],
    minAffected: 0,
    scrapedDateRange: '',
    breachDateRange: '',
    publicationDateRange: ''
  })
  const [showScraperControl, setShowScraperControl] = useState(false)
  const [showSourceSummary, setShowSourceSummary] = useState(false)
  const [showNonWorkingSites, setShowNonWorkingSites] = useState(false)

  const handleFiltersChange = useCallback((newFilters: Partial<Filters>) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
  }, [])

  const handleDateFilterChange = useCallback((dateFilters: {
    scrapedDateRange: string
    breachDateRange: string
    publicationDateRange: string
  }) => {
    setFilters(prev => ({ ...prev, ...dateFilters }))
  }, [])

  // Load counts for view toggle
  useEffect(() => {
    const loadCounts = async () => {
      try {
        // Get breach count
        const { count: breaches } = await supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .in('source_type', ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API'])

        // Get news count
        const { count: news } = await supabase
          .from('v_breach_dashboard')
          .select('*', { count: 'exact', head: true })
          .in('source_type', ['News Feed', 'Company IR'])

        setBreachCount(breaches || 0)
        setNewsCount(news || 0)
      } catch (error) {
        console.error('Failed to load counts:', error)
      }
    }

    loadCounts()
  }, [])

  return (
    <div className="space-y-6">
      {/* Control Bar */}
      <div className="flex justify-between items-center">
        <div className="flex space-x-3">
          <Button
            variant="default"
            onClick={() => setShowScraperControl(true)}
            className="bg-blue-600 hover:bg-blue-700"
          >
            🔧 Scraper Control
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowSourceSummary(true)}
          >
            📊 Source Summary
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowNonWorkingSites(true)}
            className="text-yellow-600 border-yellow-300 hover:bg-yellow-50"
          >
            ⚠️ Non-Working Sites
          </Button>
          <Button variant="outline" size="sm">
            📤 Export Data
          </Button>
          <Button variant="outline" size="sm">
            🔄 Refresh
          </Button>
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Last updated: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex justify-center">
        <ViewToggle
          currentView={currentView}
          onViewChange={setCurrentView}
          breachCount={breachCount}
          newsCount={newsCount}
        />
      </div>

      {/* Filters */}
      <FilterPanel onFiltersChange={handleFiltersChange} currentView={currentView} />

      {/* Date Filters */}
      <DateFilter onDateFilterChange={handleDateFilterChange} currentView={currentView} />

      {/* Main Content */}
      {currentView === 'breaches' ? (
        <BreachTable filters={filters} />
      ) : (
        <NewsTable filters={{
          search: filters.search,
          selectedSources: filters.selectedSources,
          scrapedDateRange: filters.scrapedDateRange,
          publicationDateRange: filters.publicationDateRange
        }} />
      )}

      {/* Modals */}
      {showScraperControl && (
        <ScraperControl onClose={() => setShowScraperControl(false)} />
      )}

      {showSourceSummary && (
        <SourceSummary onClose={() => setShowSourceSummary(false)} />
      )}

      {showNonWorkingSites && (
        <NonWorkingSites onClose={() => setShowNonWorkingSites(false)} />
      )}
    </div>
  )
}

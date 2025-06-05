import React, { useState, useCallback, useEffect } from 'react'
import { BreachTable } from './BreachTable'
import { NewsTable } from '../news/NewsTable'
import { ViewToggle, type ViewType } from './ViewToggle'
import { FilterSidebar } from '../filters/FilterSidebar'
import { FilterToggle } from '../filters/FilterToggle'
import { ActiveFilterPills, createFilterPills } from '../filters/ActiveFilterPills'
import { ScraperControl } from './ScraperControl'
import { SourceSummary } from './SourceSummary'
import { NonWorkingSites } from './NonWorkingSites'
import { SavedBreachesView } from '../saved/SavedBreachesView'
import { Button } from '../ui/Button'
import { supabase, getDataSources, getSavedBreaches } from '../../lib/supabase'

interface Filters {
  search: string
  sourceTypes: string[]
  selectedSources: number[]
  minAffected: number
  scrapedDateRange: { start?: string; end?: string }
  breachDateRange: { start?: string; end?: string }
  publicationDateRange: { start?: string; end?: string }
}

export function DashboardApp() {
  const [currentView, setCurrentView] = useState<ViewType>('breaches')
  const [breachCount, setBreachCount] = useState<number | undefined>(undefined)
  const [newsCount, setNewsCount] = useState<number | undefined>(undefined)
  const [savedCount, setSavedCount] = useState<number | undefined>(undefined)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [dataSources, setDataSources] = useState<Array<{ id: number; name: string }>>([])
  const [filters, setFilters] = useState<Filters>({
    search: '',
    sourceTypes: [],
    selectedSources: [],
    minAffected: 0,
    scrapedDateRange: {},
    breachDateRange: {},
    publicationDateRange: {}
  })
  const [showScraperControl, setShowScraperControl] = useState(false)
  const [showSourceSummary, setShowSourceSummary] = useState(false)
  const [showNonWorkingSites, setShowNonWorkingSites] = useState(false)

  const handleFiltersChange = useCallback((newFilters: Filters) => {
    setFilters(newFilters)
  }, [])

  // Load initial data
  useEffect(() => {
    const loadInitialData = async () => {
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

        // Get saved breaches count
        const savedResult = await getSavedBreaches()
        const savedBreachesCount = savedResult.data?.length || 0

        // Get data sources for filter pills
        const sourcesResult = await getDataSources()
        if (sourcesResult.data) {
          setDataSources(sourcesResult.data.map(source => ({
            id: source.id,
            name: source.name
          })))
        }

        setBreachCount(breaches || 0)
        setNewsCount(news || 0)
        setSavedCount(savedBreachesCount)
      } catch (error) {
        console.error('Failed to load initial data:', error)
      }
    }

    loadInitialData()
  }, [])

  // Create filter pills
  const filterPills = createFilterPills(filters, dataSources, {
    onSearchChange: (search) => setFilters(prev => ({ ...prev, search })),
    onSourceTypesChange: (sourceTypes) => setFilters(prev => ({ ...prev, sourceTypes })),
    onSelectedSourcesChange: (selectedSources) => setFilters(prev => ({ ...prev, selectedSources })),
    onMinAffectedChange: (minAffected) => setFilters(prev => ({ ...prev, minAffected })),
    onScrapedDateRangeChange: (scrapedDateRange) => setFilters(prev => ({ ...prev, scrapedDateRange })),
    onBreachDateRangeChange: (breachDateRange) => setFilters(prev => ({ ...prev, breachDateRange })),
    onPublicationDateRangeChange: (publicationDateRange) => setFilters(prev => ({ ...prev, publicationDateRange }))
  })

  const clearAllFilters = () => {
    setFilters({
      search: '',
      sourceTypes: [],
      selectedSources: [],
      minAffected: 0,
      scrapedDateRange: {},
      breachDateRange: {},
      publicationDateRange: {}
    })
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Filter Sidebar */}
      <FilterSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        currentView={currentView}
        onFiltersChange={handleFiltersChange}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <FilterToggle
                onClick={() => setSidebarOpen(true)}
                activeFiltersCount={filterPills.length}
              />

              <ViewToggle
                currentView={currentView}
                onViewChange={setCurrentView}
                breachCount={breachCount}
                newsCount={newsCount}
                savedCount={savedCount}
              />
            </div>

            <div className="flex items-center space-x-3">
              <Button
                variant="default"
                size="sm"
                onClick={() => setShowScraperControl(true)}
                className="bg-blue-600 hover:bg-blue-700"
              >
                🔧 Scraper Control
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSourceSummary(true)}
              >
                📊 Source Summary
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowNonWorkingSites(true)}
                className="text-yellow-600 border-yellow-300 hover:bg-yellow-50"
              >
                ⚠️ Issues
              </Button>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-full">
            {/* Active Filter Pills */}
            <ActiveFilterPills
              filters={filterPills}
              onClearAll={clearAllFilters}
            />

            {/* Main Content */}
            {currentView === 'breaches' ? (
              <BreachTable filters={{
                ...filters,
                scrapedDateRange: filters.scrapedDateRange.start || filters.scrapedDateRange.end
                  ? `${filters.scrapedDateRange.start || ''}|${filters.scrapedDateRange.end || ''}`
                  : '',
                breachDateRange: filters.breachDateRange.start || filters.breachDateRange.end
                  ? `${filters.breachDateRange.start || ''}|${filters.breachDateRange.end || ''}`
                  : '',
                publicationDateRange: filters.publicationDateRange.start || filters.publicationDateRange.end
                  ? `${filters.publicationDateRange.start || ''}|${filters.publicationDateRange.end || ''}`
                  : ''
              }} />
            ) : currentView === 'news' ? (
              <NewsTable filters={{
                search: filters.search,
                selectedSources: filters.selectedSources,
                scrapedDateRange: filters.scrapedDateRange.start || filters.scrapedDateRange.end
                  ? `${filters.scrapedDateRange.start || ''}|${filters.scrapedDateRange.end || ''}`
                  : '',
                publicationDateRange: filters.publicationDateRange.start || filters.publicationDateRange.end
                  ? `${filters.publicationDateRange.start || ''}|${filters.publicationDateRange.end || ''}`
                  : ''
              }} />
            ) : (
              <SavedBreachesView />
            )}
          </div>
        </div>
      </div>

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

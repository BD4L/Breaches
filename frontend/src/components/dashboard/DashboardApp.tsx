import React, { useState, useCallback, useEffect } from 'react'
import { BreachTable } from './BreachTable'
import { NewsTable } from '../news/NewsTable'
import { ViewToggle, type ViewType } from './ViewToggle'
import { FilterSidebar } from '../filters/FilterSidebar'
import { FilterToggle } from '../filters/FilterToggle'
import { ActiveFilterPills, createFilterPills } from '../filters/ActiveFilterPills'
import { AdminControls } from './AdminControls'
import { SavedBreachesView } from '../saved/SavedBreachesView'
import { ReportsTable } from '../reports/ReportsTable'
import { EmailStatusIndicator } from './EmailStatusIndicator'
import { supabase, getDataSources, getSavedBreaches } from '../../lib/supabase'

interface Filters {
  search: string
  sourceTypes: string[]
  selectedSources: number[]
  minAffected: number
  affectedKnown?: boolean
  noticesSent?: boolean
  scrapedDateRange: { start?: string; end?: string }
  breachDateRange: { start?: string; end?: string }
  publicationDateRange: { start?: string; end?: string }
}

export function DashboardApp() {
  const [currentView, setCurrentView] = useState<ViewType>('breaches')
  const [breachCount, setBreachCount] = useState<number | undefined>(undefined)
  const [newsCount, setNewsCount] = useState<number | undefined>(undefined)
  const [savedCount, setSavedCount] = useState<number | undefined>(undefined)
  const [reportsCount, setReportsCount] = useState<number | undefined>(undefined)

  // Handle saved count updates from BreachTable
  const handleSavedCountChange = (count: number) => {
    setSavedCount(count)
  }
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [dataSources, setDataSources] = useState<Array<{ id: number; name: string }>>([])
  const [filters, setFilters] = useState<Filters>({
    search: '',
    sourceTypes: [],
    selectedSources: [],
    minAffected: 0,
    affectedKnown: undefined,
    noticesSent: undefined,
    scrapedDateRange: {},
    breachDateRange: {},
    publicationDateRange: {}
  })


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

        // Get AI reports count
        const { count: reports } = await supabase
          .from('research_jobs')
          .select('*', { count: 'exact', head: true })

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
        setReportsCount(reports || 0)
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
    onAffectedKnownChange: (affectedKnown) => setFilters(prev => ({ ...prev, affectedKnown })),
    onNoticesSentChange: (noticesSent) => setFilters(prev => ({ ...prev, noticesSent })),
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
      affectedKnown: undefined,
      noticesSent: undefined,
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
                reportsCount={reportsCount}
              />
            </div>

            <div className="flex items-center space-x-3">
              <EmailStatusIndicator />
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-full">
            {/* Admin Controls */}
            <AdminControls />

            {/* Active Filter Pills */}
            <ActiveFilterPills
              filters={filterPills}
              onClearAll={clearAllFilters}
            />

            {/* Main Content */}
            {currentView === 'breaches' ? (
              <BreachTable
                filters={{
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
                }}
                onSavedCountChange={handleSavedCountChange}
              />
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
            ) : currentView === 'saved' ? (
              <SavedBreachesView />
            ) : (
              <ReportsTable filters={{
                search: filters.search
              }} />
            )}
          </div>
        </div>
      </div>


    </div>
  )
}

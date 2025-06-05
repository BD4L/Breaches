import React, { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Button } from '../ui/Button'
import { DateRangePicker } from './DateRangePicker'
import { SourceTypeFilter } from './SourceTypeFilter'
import { SourceFilter } from './SourceFilter'
import { AffectedSlider } from './AffectedSlider'
import { SearchInput } from './SearchInput'
import { ViewType } from '../dashboard/ViewToggle'
import { getDataSources } from '../../lib/supabase'

interface FilterSidebarProps {
  isOpen: boolean
  onClose: () => void
  currentView: ViewType
  onFiltersChange: (filters: any) => void
}

export function FilterSidebar({ isOpen, onClose, currentView, onFiltersChange }: FilterSidebarProps) {
  const [search, setSearch] = useState('')
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [selectedSources, setSelectedSources] = useState<number[]>([])
  const [minAffected, setMinAffected] = useState(0)
  const [scrapedDateRange, setScrapedDateRange] = useState<{ start?: string; end?: string }>({})
  const [breachDateRange, setBreachDateRange] = useState<{ start?: string; end?: string }>({})
  const [publicationDateRange, setPublicationDateRange] = useState<{ start?: string; end?: string }>({})
  const [dataSources, setDataSources] = useState<Array<{ id: number; name: string; source_type: string }>>([])
  const [loading, setLoading] = useState(true)

  // Load data sources
  useEffect(() => {
    const loadDataSources = async () => {
      try {
        setLoading(true)
        const result = await getDataSources()
        if (result.data) {
          setDataSources(result.data)
        }
      } catch (error) {
        console.error('Failed to load data sources:', error)
      } finally {
        setLoading(false)
      }
    }

    loadDataSources()
  }, [])

  // Update parent component with filter changes
  useEffect(() => {
    onFiltersChange({
      search,
      sourceTypes,
      selectedSources,
      minAffected,
      scrapedDateRange,
      breachDateRange,
      publicationDateRange
    })
  }, [
    search,
    sourceTypes,
    selectedSources,
    minAffected,
    scrapedDateRange,
    breachDateRange,
    publicationDateRange,
    onFiltersChange
  ])

  // Reset filters
  const handleReset = () => {
    setSearch('')
    setSourceTypes([])
    setSelectedSources([])
    setMinAffected(0)
    setScrapedDateRange({})
    setBreachDateRange({})
    setPublicationDateRange({})
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Overlay */}
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-sm" 
        onClick={onClose}
      />
      
      {/* Sidebar */}
      <div className="relative w-full max-w-xs sm:max-w-md h-full bg-dark-800 border-r border-dark-700/50 shadow-xl overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">Filters</h2>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="text-gray-400 hover:text-white hover:bg-dark-700/50"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          <div className="space-y-6">
            {/* Search */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Search</label>
              <SearchInput
                value={search}
                onChange={setSearch}
                placeholder="Search breaches..."
                className="w-full bg-dark-700 border-dark-600 text-white placeholder-gray-500 focus:border-teal"
              />
            </div>

            {/* Source Type Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Source Types</label>
              <SourceTypeFilter
                selectedTypes={sourceTypes}
                onChange={setSourceTypes}
                className="bg-dark-700 border-dark-600 text-white"
              />
            </div>

            {/* Source Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Data Sources</label>
              <SourceFilter
                sources={dataSources}
                selectedSources={selectedSources}
                onChange={setSelectedSources}
                loading={loading}
                className="bg-dark-700 border-dark-600 text-white"
              />
            </div>

            {/* Affected Individuals Slider - only show for breach view */}
            {currentView === 'breaches' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Minimum Affected Individuals</label>
                <AffectedSlider
                  value={minAffected}
                  onChange={setMinAffected}
                  className="text-teal"
                />
                <div className="text-xs text-gray-400 mt-1">
                  {minAffected === 0 
                    ? 'Show all breaches' 
                    : `Minimum: ${minAffected.toLocaleString()} affected`}
                </div>
              </div>
            )}

            {/* Date Range Filters */}
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Scraped Date Range</label>
                <DateRangePicker
                  startDate={scrapedDateRange.start}
                  endDate={scrapedDateRange.end}
                  onChange={(start, end) => setScrapedDateRange({ start, end })}
                  className="bg-dark-700 border-dark-600 text-white"
                />
              </div>

              {currentView === 'breaches' && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-300">Breach Date Range</label>
                  <DateRangePicker
                    startDate={breachDateRange.start}
                    endDate={breachDateRange.end}
                    onChange={(start, end) => setBreachDateRange({ start, end })}
                    className="bg-dark-700 border-dark-600 text-white"
                  />
                </div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Publication Date Range</label>
                <DateRangePicker
                  startDate={publicationDateRange.start}
                  endDate={publicationDateRange.end}
                  onChange={(start, end) => setPublicationDateRange({ start, end })}
                  className="bg-dark-700 border-dark-600 text-white"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-dark-700">
              <Button
                variant="outline"
                size="sm"
                onClick={handleReset}
                className="border-dark-600 text-gray-300 hover:bg-dark-700/50"
              >
                Reset All
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={onClose}
                className="bg-teal hover:bg-teal-light text-dark-900 font-medium"
              >
                Apply Filters
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

import React, { useState, useCallback } from 'react'
import { FilterPanel } from '../filters/FilterPanel'
import { DateFilter } from '../filters/DateFilter'
import { PresetFilters } from '../filters/PresetFilters'
import { BreachTable } from './BreachTable'
import { ScraperControl } from './ScraperControl'
import { SourceSummary } from './SourceSummary'
import { Button } from '../ui/Button'

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

  const handlePresetApplied = useCallback((preset: {
    name: string
    sourceTypes: string[]
    selectedSources: number[]
    scrapedDateRange: string
    breachDateRange: string
    publicationDateRange: string
  }) => {
    setFilters(prev => ({
      ...prev,
      sourceTypes: preset.sourceTypes,
      selectedSources: preset.selectedSources,
      scrapedDateRange: preset.scrapedDateRange,
      breachDateRange: preset.breachDateRange,
      publicationDateRange: preset.publicationDateRange
    }))
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

      {/* Quick Preset Filters */}
      <PresetFilters onPresetApplied={handlePresetApplied} />

      {/* Filters */}
      <FilterPanel
        onFiltersChange={handleFiltersChange}
        externalFilters={{
          search: filters.search,
          sourceTypes: filters.sourceTypes,
          selectedSources: filters.selectedSources,
          minAffected: filters.minAffected
        }}
      />

      {/* Date Filters */}
      <DateFilter
        onDateFilterChange={handleDateFilterChange}
        externalFilters={{
          scrapedDateRange: filters.scrapedDateRange,
          breachDateRange: filters.breachDateRange,
          publicationDateRange: filters.publicationDateRange
        }}
      />

      {/* Main Table */}
      <BreachTable filters={filters} />

      {/* Modals */}
      {showScraperControl && (
        <ScraperControl onClose={() => setShowScraperControl(false)} />
      )}

      {showSourceSummary && (
        <SourceSummary onClose={() => setShowSourceSummary(false)} />
      )}
    </div>
  )
}

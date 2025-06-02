import React, { useState, useCallback } from 'react'
import { FilterPanel } from '../filters/FilterPanel'
import { BreachTable } from './BreachTable'
import { ScraperControl } from './ScraperControl'
import { Button } from '../ui/Button'

interface Filters {
  search: string
  sourceTypes: string[]
  minAffected: number
}

export function DashboardApp() {
  const [filters, setFilters] = useState<Filters>({
    search: '',
    sourceTypes: [],
    minAffected: 0
  })
  const [showScraperControl, setShowScraperControl] = useState(false)

  const handleFiltersChange = useCallback((newFilters: Filters) => {
    setFilters(newFilters)
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
          <Button variant="outline" size="sm">
            📊 Export Data
          </Button>
          <Button variant="outline" size="sm">
            🔄 Refresh
          </Button>
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Last updated: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* Filters */}
      <FilterPanel onFiltersChange={handleFiltersChange} />

      {/* Main Table */}
      <BreachTable filters={filters} />

      {/* Scraper Control Modal */}
      {showScraperControl && (
        <ScraperControl onClose={() => setShowScraperControl(false)} />
      )}
    </div>
  )
}

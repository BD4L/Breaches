import React, { useState, useCallback } from 'react'
import { FilterPanel } from '../filters/FilterPanel'
import { BreachTable } from './BreachTable'

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

  const handleFiltersChange = useCallback((newFilters: Filters) => {
    setFilters(newFilters)
  }, [])

  return (
    <div className="space-y-6">
      {/* Filters */}
      <FilterPanel onFiltersChange={handleFiltersChange} />
      
      {/* Main Table */}
      <BreachTable filters={filters} />
    </div>
  )
}

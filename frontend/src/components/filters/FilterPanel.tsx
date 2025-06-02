import React, { useState, useEffect } from 'react'
import { Input } from '../ui/Input'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { getSourceTypes, getSourceTypeCounts } from '../../lib/supabase'
import { getSourceTypeColor } from '../../lib/utils'

interface FilterPanelProps {
  onFiltersChange: (filters: {
    search: string
    sourceTypes: string[]
    minAffected: number
  }) => void
}

export function FilterPanel({ onFiltersChange }: FilterPanelProps) {
  const [search, setSearch] = useState('')
  const [selectedSourceTypes, setSelectedSourceTypes] = useState<string[]>([])
  const [minAffected, setMinAffected] = useState(0)
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [sourceTypeCounts, setSourceTypeCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadFilterOptions() {
      try {
        const [types, counts] = await Promise.all([
          getSourceTypes(),
          getSourceTypeCounts()
        ])
        setSourceTypes(types)
        setSourceTypeCounts(counts)
      } catch (error) {
        console.error('Error loading filter options:', error)
      } finally {
        setLoading(false)
      }
    }

    loadFilterOptions()
  }, [])

  useEffect(() => {
    onFiltersChange({
      search,
      sourceTypes: selectedSourceTypes,
      minAffected
    })
  }, [search, selectedSourceTypes, minAffected, onFiltersChange])

  const toggleSourceType = (type: string) => {
    setSelectedSourceTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    )
  }

  const clearFilters = () => {
    setSearch('')
    setSelectedSourceTypes([])
    setMinAffected(0)
  }

  const affectedThresholds = [
    { label: 'Any', value: 0 },
    { label: '1K+', value: 1000 },
    { label: '10K+', value: 10000 },
    { label: '100K+', value: 100000 },
    { label: '1M+', value: 1000000 }
  ]

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="flex space-x-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="space-y-6">
        {/* Search */}
        <div>
          <label htmlFor="search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Search Organizations
          </label>
          <Input
            id="search"
            type="text"
            placeholder="Search by organization name or leaked data..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Source Types */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Source Types
          </label>
          <div className="flex flex-wrap gap-2">
            {sourceTypes.map(type => (
              <button
                key={type}
                onClick={() => toggleSourceType(type)}
                className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                  selectedSourceTypes.includes(type)
                    ? 'bg-blue-600 text-white'
                    : getSourceTypeColor(type)
                } hover:opacity-80`}
              >
                {type}
                <span className="ml-1 text-xs opacity-75">
                  ({sourceTypeCounts[type] || 0})
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Affected Individuals Threshold */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Minimum Affected Individuals
          </label>
          <div className="flex flex-wrap gap-2">
            {affectedThresholds.map(threshold => (
              <button
                key={threshold.value}
                onClick={() => setMinAffected(threshold.value)}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                  minAffected === threshold.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {threshold.label}
              </button>
            ))}
          </div>
        </div>

        {/* Active Filters & Clear */}
        {(search || selectedSourceTypes.length > 0 || minAffected > 0) && (
          <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
            <div className="flex flex-wrap gap-2">
              {search && (
                <Badge variant="outline">
                  Search: "{search}"
                </Badge>
              )}
              {selectedSourceTypes.map(type => (
                <Badge key={type} variant="outline">
                  {type}
                </Badge>
              ))}
              {minAffected > 0 && (
                <Badge variant="outline">
                  Min: {minAffected.toLocaleString()}+
                </Badge>
              )}
            </div>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear All
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

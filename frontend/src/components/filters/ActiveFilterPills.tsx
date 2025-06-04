import React from 'react'
import { X, Calendar, Users, Search, Filter } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'

interface FilterPill {
  id: string
  label: string
  value: string
  type: 'search' | 'date' | 'numeric' | 'source' | 'category'
  onRemove: () => void
}

interface ActiveFilterPillsProps {
  filters: FilterPill[]
  onClearAll: () => void
}

export function ActiveFilterPills({ filters, onClearAll }: ActiveFilterPillsProps) {
  if (filters.length === 0) {
    return null
  }

  const getIcon = (type: FilterPill['type']) => {
    switch (type) {
      case 'search':
        return <Search className="w-3 h-3" />
      case 'date':
        return <Calendar className="w-3 h-3" />
      case 'numeric':
        return <Users className="w-3 h-3" />
      case 'source':
      case 'category':
        return <Filter className="w-3 h-3" />
      default:
        return null
    }
  }

  const getColorClass = (type: FilterPill['type']) => {
    switch (type) {
      case 'search':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'date':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'numeric':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      case 'source':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      case 'category':
        return 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center">
          <Filter className="w-4 h-4 mr-2" />
          Active Filters ({filters.length})
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearAll}
          className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
        >
          Clear All
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {filters.map((filter) => (
          <div
            key={filter.id}
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${getColorClass(filter.type)}`}
          >
            {getIcon(filter.type)}
            <span className="font-medium">{filter.label}:</span>
            <span>{filter.value}</span>
            <button
              onClick={filter.onRemove}
              className="ml-1 hover:bg-black hover:bg-opacity-10 rounded-full p-0.5 transition-colors"
              aria-label={`Remove ${filter.label} filter`}
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// Helper function to create filter pills from filter state
export function createFilterPills(
  filters: {
    search: string
    sourceTypes: string[]
    selectedSources: number[]
    minAffected: number
    scrapedDateRange: { start?: string; end?: string }
    breachDateRange: { start?: string; end?: string }
    publicationDateRange: { start?: string; end?: string }
  },
  sources: Array<{ id: number; name: string }>,
  onFilterChange: {
    onSearchChange: (search: string) => void
    onSourceTypesChange: (types: string[]) => void
    onSelectedSourcesChange: (sources: number[]) => void
    onMinAffectedChange: (min: number) => void
    onScrapedDateRangeChange: (range: { start?: string; end?: string }) => void
    onBreachDateRangeChange: (range: { start?: string; end?: string }) => void
    onPublicationDateRangeChange: (range: { start?: string; end?: string }) => void
  }
): FilterPill[] {
  const pills: FilterPill[] = []

  // Search filter
  if (filters.search) {
    pills.push({
      id: 'search',
      label: 'Search',
      value: `"${filters.search}"`,
      type: 'search',
      onRemove: () => onFilterChange.onSearchChange('')
    })
  }

  // Source type filters
  filters.sourceTypes.forEach((type) => {
    pills.push({
      id: `source-type-${type}`,
      label: 'Category',
      value: type,
      type: 'category',
      onRemove: () => onFilterChange.onSourceTypesChange(filters.sourceTypes.filter(t => t !== type))
    })
  })

  // Individual source filters
  filters.selectedSources.forEach((sourceId) => {
    const source = sources.find(s => s.id === sourceId)
    if (source) {
      pills.push({
        id: `source-${sourceId}`,
        label: 'Source',
        value: source.name,
        type: 'source',
        onRemove: () => onFilterChange.onSelectedSourcesChange(filters.selectedSources.filter(id => id !== sourceId))
      })
    }
  })

  // Minimum affected filter
  if (filters.minAffected > 0) {
    pills.push({
      id: 'min-affected',
      label: 'Min Affected',
      value: `${filters.minAffected.toLocaleString()}+ people`,
      type: 'numeric',
      onRemove: () => onFilterChange.onMinAffectedChange(0)
    })
  }

  // Date range filters
  const formatDateRange = (range: { start?: string; end?: string }) => {
    if (range.start && range.end) {
      return `${new Date(range.start).toLocaleDateString()} - ${new Date(range.end).toLocaleDateString()}`
    } else if (range.start) {
      return `From ${new Date(range.start).toLocaleDateString()}`
    } else if (range.end) {
      return `Until ${new Date(range.end).toLocaleDateString()}`
    }
    return ''
  }

  if (filters.scrapedDateRange.start || filters.scrapedDateRange.end) {
    pills.push({
      id: 'scraped-date',
      label: 'Scraped Date',
      value: formatDateRange(filters.scrapedDateRange),
      type: 'date',
      onRemove: () => onFilterChange.onScrapedDateRangeChange({ start: undefined, end: undefined })
    })
  }

  if (filters.breachDateRange.start || filters.breachDateRange.end) {
    pills.push({
      id: 'breach-date',
      label: 'Breach Date',
      value: formatDateRange(filters.breachDateRange),
      type: 'date',
      onRemove: () => onFilterChange.onBreachDateRangeChange({ start: undefined, end: undefined })
    })
  }

  if (filters.publicationDateRange.start || filters.publicationDateRange.end) {
    pills.push({
      id: 'publication-date',
      label: 'Publication Date',
      value: formatDateRange(filters.publicationDateRange),
      type: 'date',
      onRemove: () => onFilterChange.onPublicationDateRangeChange({ start: undefined, end: undefined })
    })
  }

  return pills
}

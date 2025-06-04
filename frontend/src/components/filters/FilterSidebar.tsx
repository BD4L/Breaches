import React, { useState, useEffect, useRef, useCallback } from 'react'
import { X, Filter, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { DateRangePicker } from './DateRangePicker'
import { NumericSlider } from './NumericSlider'
import { SourceSelector } from './SourceSelector'
import { getSourceTypes, getSourceTypeCounts, getSourcesByCategory, isNewsSource, isBreachSource } from '../../lib/supabase'
import { getSourceTypeColor } from '../../lib/utils'
import type { ViewType } from '../dashboard/ViewToggle'

// Move SectionHeader outside to prevent remounting
const SectionHeader = ({
  title,
  section,
  children,
  expandedSections,
  onToggle
}: {
  title: string
  section: string
  children: React.ReactNode
  expandedSections: Record<string, boolean>
  onToggle: (section: string) => void
}) => (
  <div className="space-y-3">
    <button
      onClick={() => onToggle(section)}
      className="flex items-center justify-between w-full text-left"
    >
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">{title}</h3>
      {expandedSections[section] ? (
        <ChevronDown className="w-4 h-4 text-gray-400" />
      ) : (
        <ChevronRight className="w-4 h-4 text-gray-400" />
      )}
    </button>
    {expandedSections[section] && <div className="space-y-3">{children}</div>}
  </div>
)

interface FilterSidebarProps {
  isOpen: boolean
  onClose: () => void
  currentView: ViewType
  onFiltersChange: (filters: {
    search: string
    sourceTypes: string[]
    selectedSources: number[]
    minAffected: number
    scrapedDateRange: { start?: string; end?: string }
    breachDateRange: { start?: string; end?: string }
    publicationDateRange: { start?: string; end?: string }
  }) => void
}

export function FilterSidebar({ isOpen, onClose, currentView, onFiltersChange }: FilterSidebarProps) {
  const [search, setSearch] = useState('')
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [selectedSources, setSelectedSources] = useState<number[]>([])
  const [minAffected, setMinAffected] = useState(0)
  const [scrapedDateRange, setScrapedDateRange] = useState<{ start?: string; end?: string }>({})
  const [breachDateRange, setBreachDateRange] = useState<{ start?: string; end?: string }>({})
  const [publicationDateRange, setPublicationDateRange] = useState<{ start?: string; end?: string }>({})

  // Use refs to prevent re-renders during typing
  const searchTimeoutRef = useRef<NodeJS.Timeout>()
  const lastSearchRef = useRef('')

  // Collapsible sections
  const [expandedSections, setExpandedSections] = useState({
    search: true,
    dates: true,
    sources: true,
    affected: currentView === 'breaches'
  })

  // Available source types and counts
  const [availableSourceTypes, setAvailableSourceTypes] = useState<string[]>([])
  const [sourceTypeCounts, setSourceTypeCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    loadSourceTypes()
  }, [currentView])

  // Handle search input with debouncing
  const handleSearchChange = (value: string) => {
    setSearch(value)

    // Clear existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    // Set new timeout for search
    searchTimeoutRef.current = setTimeout(() => {
      if (lastSearchRef.current !== value) {
        lastSearchRef.current = value
        onFiltersChange({
          search: value,
          sourceTypes,
          selectedSources,
          minAffected,
          scrapedDateRange,
          breachDateRange,
          publicationDateRange
        })
      }
    }, 500) // Increased debounce time
  }

  // Update filters immediately for non-search changes
  const updateFiltersImmediate = useCallback(() => {
    onFiltersChange({
      search: lastSearchRef.current || search,
      sourceTypes,
      selectedSources,
      minAffected,
      scrapedDateRange,
      breachDateRange,
      publicationDateRange
    })
  }, [onFiltersChange, search, sourceTypes, selectedSources, minAffected, scrapedDateRange, breachDateRange, publicationDateRange])

  // Effect for non-search filters
  useEffect(() => {
    updateFiltersImmediate()
  }, [updateFiltersImmediate])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [])

  const loadSourceTypes = async () => {
    try {
      const [typesResult, countsResult] = await Promise.all([
        getSourceTypes(),
        getSourceTypeCounts()
      ])

      if (typesResult.data && countsResult.data) {
        // Filter source types based on current view
        const filteredTypes = typesResult.data.filter(type => {
          if (currentView === 'breaches') {
            return !['RSS News Feeds', 'Company IR Sites'].includes(type)
          } else {
            return ['RSS News Feeds', 'Company IR Sites'].includes(type)
          }
        })

        setAvailableSourceTypes(filteredTypes)
        
        const counts: Record<string, number> = {}
        countsResult.data.forEach(item => {
          counts[item.type] = item.count
        })
        setSourceTypeCounts(counts)
      }
    } catch (error) {
      console.error('Failed to load source types:', error)
    }
  }

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const clearAllFilters = () => {
    setSearch('')
    setSourceTypes([])
    setSelectedSources([])
    setMinAffected(0)
    setScrapedDateRange({})
    setBreachDateRange({})
    setPublicationDateRange({})
  }



  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-50 lg:hidden"
          onClick={onClose}
          style={{ zIndex: 60 }}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed lg:static inset-y-0 left-0 w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700
          transform transition-transform duration-300 ease-in-out lg:transform-none
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col h-full shadow-2xl lg:shadow-none
        `}
        style={{ zIndex: 70 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <Filter className="w-5 h-5 mr-2" />
            Filters
          </h2>
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAllFilters}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Clear All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="lg:hidden p-1"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* Filter Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Search */}
          <SectionHeader
            title="Search"
            section="search"
            expandedSections={expandedSections}
            onToggle={toggleSection}
          >
            <Input
              type="text"
              placeholder={currentView === 'breaches'
                ? "Search organizations, data types..."
                : "Search articles, content..."
              }
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </SectionHeader>

          {/* Date Filters */}
          <SectionHeader
            title="Date Ranges"
            section="dates"
            expandedSections={expandedSections}
            onToggle={toggleSection}
          >
            <DateRangePicker
              label="Scraped Date"
              value={scrapedDateRange}
              onChange={setScrapedDateRange}
            />

            {currentView === 'breaches' && (
              <DateRangePicker
                label="Breach Date"
                value={breachDateRange}
                onChange={setBreachDateRange}
              />
            )}

            <DateRangePicker
              label="Publication Date"
              value={publicationDateRange}
              onChange={setPublicationDateRange}
            />
          </SectionHeader>

          {/* Affected Individuals - Only for breach view */}
          {currentView === 'breaches' && (
            <SectionHeader
              title="People Affected"
              section="affected"
              expandedSections={expandedSections}
              onToggle={toggleSection}
            >
              <NumericSlider
                label="Minimum Affected"
                value={minAffected}
                onChange={setMinAffected}
                min={0}
                max={100000}
                step={100}
              />
            </SectionHeader>
          )}

          {/* Source Categories */}
          <SectionHeader
            title="Source Categories"
            section="sources"
            expandedSections={expandedSections}
            onToggle={toggleSection}
          >
            <div className="space-y-3">
              {availableSourceTypes.map(type => {
                const count = sourceTypeCounts[type] || 0
                const isSelected = sourceTypes.includes(type)
                
                return (
                  <div key={type} className="flex items-center justify-between">
                    <button
                      onClick={() => {
                        if (isSelected) {
                          setSourceTypes(prev => prev.filter(t => t !== type))
                        } else {
                          setSourceTypes(prev => [...prev, type])
                        }
                      }}
                      className={`flex-1 text-left p-2 rounded-md transition-colors ${
                        isSelected
                          ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                          : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {type}
                        </span>
                        <Badge className={getSourceTypeColor(type)}>
                          {count.toLocaleString()}
                        </Badge>
                      </div>
                    </button>
                  </div>
                )
              })}
            </div>

            {/* Individual Source Selection */}
            {sourceTypes.length > 0 && (
              <div className="mt-4">
                <SourceSelector
                  selectedSourceTypes={sourceTypes}
                  selectedSources={selectedSources}
                  onSourcesChange={setSelectedSources}
                />
              </div>
            )}
          </SectionHeader>
        </div>
      </div>
    </>
  )
}

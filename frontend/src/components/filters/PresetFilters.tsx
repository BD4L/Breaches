import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { getSourcesByCategory } from '../../lib/supabase'

interface PresetFiltersProps {
  onPresetApplied: (preset: {
    name: string
    sourceTypes: string[]
    selectedSources: number[]
    scrapedDateRange: string
    breachDateRange: string
    publicationDateRange: string
  }) => void
}

interface Source {
  id: number
  name: string
  originalType: string
  itemCount: number
  itemType: string
}

export function PresetFilters({ onPresetApplied }: PresetFiltersProps) {
  const [sourcesByCategory, setSourcesByCategory] = useState<Record<string, Source[]>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSources()
  }, [])

  const loadSources = async () => {
    try {
      setLoading(true)
      const sources = await getSourcesByCategory()
      setSourcesByCategory(sources)
    } catch (error) {
      console.error('Failed to load sources for presets:', error)
    } finally {
      setLoading(false)
    }
  }

  const applyBreachesOfTheDay = () => {
    // Get all State AG Sites (all AG portals)
    const agSources = sourcesByCategory['State AG Sites'] || []
    const agSourceIds = agSources.map(source => source.id)

    // Get HHS OCR from Government Portals (source ID 2)
    const govSources = sourcesByCategory['Government Portals'] || []
    const hhsOcr = govSources.find(source => source.name.includes('HHS OCR'))
    const hhsOcrId = hhsOcr ? [hhsOcr.id] : [2] // Fallback to ID 2 if not found

    // Combine all source IDs
    const selectedSources = [...agSourceIds, ...hhsOcrId]

    onPresetApplied({
      name: 'Breaches Of The Day',
      sourceTypes: [], // Using specific sources instead of types
      selectedSources,
      scrapedDateRange: 'today',
      breachDateRange: '',
      publicationDateRange: ''
    })
  }

  const presets = [
    {
      name: 'Breaches Of The Day',
      description: 'All AG portals + HHS OCR from today',
      icon: '🚨',
      action: applyBreachesOfTheDay,
      color: 'bg-red-600 hover:bg-red-700 text-white'
    },
    // Future presets can be added here
  ]

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center space-x-2 mb-3">
          <span className="text-lg">⚡</span>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Quick Filters</h3>
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">Loading presets...</div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center space-x-2 mb-3">
        <span className="text-lg">⚡</span>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Quick Filters</h3>
      </div>
      
      <div className="space-y-2">
        {presets.map((preset, index) => (
          <div key={index} className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-lg">{preset.icon}</span>
              <div>
                <div className="font-medium text-gray-900 dark:text-white">
                  {preset.name}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {preset.description}
                </div>
              </div>
            </div>
            <Button
              onClick={preset.action}
              className={preset.color}
              size="sm"
            >
              Apply
            </Button>
          </div>
        ))}
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Quick filters automatically set source and date combinations for common use cases.
        </div>
      </div>
    </div>
  )
}

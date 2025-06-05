import React, { useState, useEffect } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { getSourceTypes, getSourceTypeCounts } from '../../lib/supabase'
import { getSourceTypeColor } from '../../lib/utils'

interface SourceTypeFilterProps {
  selectedTypes: string[]
  onChange: (types: string[]) => void
  className?: string
}

export function SourceTypeFilter({ selectedTypes, onChange, className = '' }: SourceTypeFilterProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadSourceTypes = async () => {
      try {
        setLoading(true)
        const [typesResult, countsResult] = await Promise.all([
          getSourceTypes(),
          getSourceTypeCounts()
        ])

        if (typesResult.data && countsResult.data) {
          setSourceTypes(typesResult.data)
          
          const counts: Record<string, number> = {}
          countsResult.data.forEach(item => {
            counts[item.type] = item.count
          })
          setTypeCounts(counts)
        }
      } catch (error) {
        console.error('Failed to load source types:', error)
      } finally {
        setLoading(false)
      }
    }

    loadSourceTypes()
  }, [])

  const toggleSourceType = (type: string) => {
    if (selectedTypes.includes(type)) {
      onChange(selectedTypes.filter(t => t !== type))
    } else {
      onChange([...selectedTypes, type])
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center justify-between w-full px-4 py-2 text-left rounded-lg border ${
          selectedTypes.length > 0 
            ? 'border-teal/50 bg-teal/10' 
            : 'border-dark-600 bg-dark-700'
        } ${className}`}
      >
        <span className="block truncate">
          {selectedTypes.length === 0
            ? 'Select source types...'
            : `${selectedTypes.length} type${selectedTypes.length > 1 ? 's' : ''} selected`}
        </span>
        <ChevronDown className="w-4 h-4 ml-2" />
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-dark-800 border border-dark-600 rounded-lg shadow-lg max-h-60 overflow-auto">
          <div className="p-2 space-y-1">
            {loading ? (
              <div className="text-center py-2 text-gray-400">Loading...</div>
            ) : (
              sourceTypes.map(type => {
                const count = typeCounts[type] || 0
                const isSelected = selectedTypes.includes(type)
                
                return (
                  <button
                    key={type}
                    onClick={() => toggleSourceType(type)}
                    className={`flex items-center justify-between w-full px-3 py-2 text-left rounded-md ${
                      isSelected 
                        ? 'bg-teal/20 text-white' 
                        : 'hover:bg-dark-700 text-gray-300'
                    }`}
                  >
                    <div className="flex items-center">
                      <div className={`w-4 h-4 mr-2 flex items-center justify-center rounded border ${
                        isSelected 
                          ? 'bg-teal border-teal' 
                          : 'border-gray-500'
                      }`}>
                        {isSelected && <Check className="w-3 h-3 text-dark-900" />}
                      </div>
                      <span>{type}</span>
                    </div>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${getSourceTypeColor(type)}`}>
                      {count}
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
} 
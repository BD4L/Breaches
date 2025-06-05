import React from 'react'
import { Filter } from 'lucide-react'
import { Button } from '../ui/Button'

interface FilterToggleProps {
  onClick: () => void
  activeFiltersCount?: number
}

export function FilterToggle({ onClick, activeFiltersCount = 0 }: FilterToggleProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      className="relative border-dark-600 text-gray-300 hover:bg-dark-700/50"
    >
      <Filter className="w-4 h-4 mr-2" />
      Filters
      {activeFiltersCount > 0 && (
        <span className="absolute -top-2 -right-2 bg-teal text-dark-900 text-xs font-medium rounded-full h-5 w-5 flex items-center justify-center shadow-glow-teal">
          {activeFiltersCount > 9 ? '9+' : activeFiltersCount}
        </span>
      )}
    </Button>
  )
}

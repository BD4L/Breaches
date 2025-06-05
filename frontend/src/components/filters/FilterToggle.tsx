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
      className="lg:hidden relative"
    >
      <Filter className="w-4 h-4 mr-2" />
      Filters
      {activeFiltersCount > 0 && (
        <span className="absolute -top-2 -right-2 bg-blue-600 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
          {activeFiltersCount > 9 ? '9+' : activeFiltersCount}
        </span>
      )}
    </Button>
  )
}

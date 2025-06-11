import React from 'react'
import { Users, AlertTriangle } from 'lucide-react'
import { Badge } from '../ui/Badge'

interface AffectedPeopleIndicatorProps {
  minAffected: number
  affectedKnown?: boolean
  className?: string
}

export function AffectedPeopleIndicator({ 
  minAffected, 
  affectedKnown, 
  className = '' 
}: AffectedPeopleIndicatorProps) {
  const formatCount = (count: number) => {
    if (count === 0) return 'Any'
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M+`
    if (count >= 1000) return `${(count / 1000).toFixed(0)}K+`
    return `${count.toLocaleString()}+`
  }

  const getImpactLevel = (threshold: number) => {
    if (threshold === 0) return { label: 'All', color: 'gray', bgColor: 'bg-gray-100', textColor: 'text-gray-800', borderColor: 'border-gray-200' }
    if (threshold >= 100000) return { label: 'Critical', color: 'red', bgColor: 'bg-red-100', textColor: 'text-red-800', borderColor: 'border-red-200' }
    if (threshold >= 10000) return { label: 'High', color: 'orange', bgColor: 'bg-orange-100', textColor: 'text-orange-800', borderColor: 'border-orange-200' }
    if (threshold >= 1000) return { label: 'Medium', color: 'yellow', bgColor: 'bg-yellow-100', textColor: 'text-yellow-800', borderColor: 'border-yellow-200' }
    return { label: 'Low', color: 'green', bgColor: 'bg-green-100', textColor: 'text-green-800', borderColor: 'border-green-200' }
  }

  const impact = getImpactLevel(minAffected)
  const hasFilter = minAffected > 0 || affectedKnown !== undefined

  if (!hasFilter) {
    return null
  }

  return (
    <div className={`inline-flex items-center space-x-2 px-3 py-2 rounded-lg border ${impact.bgColor} ${impact.textColor} ${impact.borderColor} ${className}`}>
      <Users className="w-4 h-4" />
      <div className="flex items-center space-x-2">
        <span className="text-sm font-medium">
          {formatCount(minAffected)} people
        </span>
        
        {minAffected > 0 && (
          <Badge className={`text-xs ${impact.bgColor} ${impact.textColor} ${impact.borderColor}`}>
            {impact.label}
          </Badge>
        )}
        
        {affectedKnown !== undefined && (
          <Badge className="text-xs bg-blue-100 text-blue-800 border-blue-200">
            {affectedKnown ? 'Known' : 'Unknown'} counts
          </Badge>
        )}
      </div>
      
      {minAffected >= 10000 && (
        <AlertTriangle className="w-4 h-4 text-orange-600" />
      )}
    </div>
  )
}

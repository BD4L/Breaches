import React from 'react'
import { Button } from '../ui/Button'

export type ViewType = 'breaches' | 'news'

interface ViewToggleProps {
  currentView: ViewType
  onViewChange: (view: ViewType) => void
  breachCount?: number
  newsCount?: number
}

export function ViewToggle({ currentView, onViewChange, breachCount, newsCount }: ViewToggleProps) {
  return (
    <div className="flex items-center space-x-1 bg-dark-700/50 p-1 rounded-lg">
      <Button
        variant={currentView === 'breaches' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('breaches')}
        className={`flex items-center space-x-2 ${
          currentView === 'breaches'
            ? 'bg-dark-800 text-white border border-dark-600'
            : 'hover:bg-dark-700 text-gray-400'
        }`}
      >
        <span>🚨</span>
        <span>Breach Notifications</span>
        {breachCount !== undefined && (
          <span className="ml-1 px-2 py-0.5 text-xs bg-purple/20 text-purple-light rounded-full">
            {breachCount.toLocaleString()}
          </span>
        )}
      </Button>
      
      <Button
        variant={currentView === 'news' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('news')}
        className={`flex items-center space-x-2 ${
          currentView === 'news'
            ? 'bg-dark-800 text-white border border-dark-600'
            : 'hover:bg-dark-700 text-gray-400'
        }`}
      >
        <span>📰</span>
        <span>Cybersecurity News</span>
        {newsCount !== undefined && (
          <span className="ml-1 px-2 py-0.5 text-xs bg-teal/20 text-teal-light rounded-full">
            {newsCount.toLocaleString()}
          </span>
        )}
      </Button>
    </div>
  )
}

import React, { useState } from 'react'
import { Button } from '../ui/Button'
import { ScraperControl } from './ScraperControl'
import { SourceSummary } from './SourceSummary'
import { NonWorkingSites } from './NonWorkingSites'
import { Settings, Database, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'

export function AdminControls() {
  const [isExpanded, setIsExpanded] = useState(false)
  const [showScraperControl, setShowScraperControl] = useState(false)
  const [showSourceSummary, setShowSourceSummary] = useState(false)
  const [showNonWorkingSites, setShowNonWorkingSites] = useState(false)

  return (
    <>
      {/* Admin Controls Section */}
      <div className="mb-6 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="px-4 py-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full flex items-center justify-between text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
          >
            <div className="flex items-center space-x-2">
              <Settings className="w-4 h-4" />
              <span className="font-medium">Admin Controls</span>
            </div>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </Button>
          
          {isExpanded && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowScraperControl(true)}
                className="flex items-center space-x-2"
              >
                <Settings className="w-4 h-4" />
                <span>Scraper Control</span>
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSourceSummary(true)}
                className="flex items-center space-x-2"
              >
                <Database className="w-4 h-4" />
                <span>Source Summary</span>
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowNonWorkingSites(true)}
                className="flex items-center space-x-2"
              >
                <AlertTriangle className="w-4 h-4" />
                <span>Non-Working Sites</span>
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      {showScraperControl && (
        <ScraperControl onClose={() => setShowScraperControl(false)} />
      )}

      {showSourceSummary && (
        <SourceSummary onClose={() => setShowSourceSummary(false)} />
      )}

      {showNonWorkingSites && (
        <NonWorkingSites onClose={() => setShowNonWorkingSites(false)} />
      )}
    </>
  )
}

import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { ScheduleManager } from './ScheduleManager'

interface ScraperGroup {
  id: string
  name: string
  description: string
  scrapers: string[]
  schedule: string
  lastRun?: string
  status: 'idle' | 'running' | 'success' | 'failed'
  canTrigger: boolean
}

interface ScraperControlProps {
  onClose: () => void
}

export function ScraperControl({ onClose }: ScraperControlProps) {
  const [scraperGroups, setScraperGroups] = useState<ScraperGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState<string | null>(null)
  const [showScheduleManager, setShowScheduleManager] = useState(false)

  // Define scraper groups based on new categorization (Government Portals, AG Sites, RSS News Feeds)
  const defaultScraperGroups: ScraperGroup[] = [
    {
      id: 'government-portals',
      name: '🏢 Government Portals',
      description: 'Federal agencies and government breach reporting',
      scrapers: ['SEC EDGAR 8-K', 'HHS OCR Breach Portal'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-1',
      name: '🏛️ State AG Group 1',
      description: 'Delaware, California, Washington, Hawaii',
      scrapers: ['Delaware AG', 'California AG', 'Washington AG', 'Hawaii AG'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-2',
      name: '🏛️ State AG Group 2',
      description: 'Indiana, Iowa, Maine',
      scrapers: ['Indiana AG', 'Iowa AG', 'Maine AG'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-3',
      name: '🏛️ State AG Group 3',
      description: 'Massachusetts, Montana',
      scrapers: ['Massachusetts AG', 'Montana AG'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-4',
      name: '🏛️ State AG Group 4',
      description: 'North Dakota, Oklahoma, Vermont, Wisconsin, Texas',
      scrapers: ['North Dakota AG', 'Oklahoma Cyber', 'Vermont AG', 'Wisconsin DATCP', 'Texas AG'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'rss-news-feeds',
      name: '📰 RSS News Feeds',
      description: 'Cybersecurity news, breach databases, and HIBP RSS',
      scrapers: ['KrebsOnSecurity', 'BleepingComputer', 'The Hacker News', 'SecurityWeek', 'Dark Reading', 'DataBreaches.net', 'HIBP RSS', 'CISA News', 'Security Magazine'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'specialized-sites',
      name: '🔍 Specialized Breach Sites',
      description: 'Dedicated breach tracking platforms',
      scrapers: ['BreachSense'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'company-ir-sites',
      name: '💼 Company IR Sites',
      description: 'Major tech company investor relations',
      scrapers: ['Microsoft IR', 'Apple IR', 'Amazon IR', 'Alphabet IR', 'Meta IR'],
      schedule: 'Daily at 3 AM UTC',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'massachusetts-ag-frequent',
      name: '🏛️ Massachusetts AG (High Frequency)',
      description: 'High-priority state with 6-hour monitoring',
      scrapers: ['Massachusetts AG'],
      schedule: 'Every 6 hours',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'problematic-scrapers',
      name: '⚠️ Problematic Scrapers',
      description: 'Sources with known technical issues',
      scrapers: ['Maryland AG', 'New Hampshire AG', 'New Jersey AG'],
      schedule: 'Daily at 3 AM UTC (Continue on Error)',
      status: 'idle',
      canTrigger: true
    }
  ]

  useEffect(() => {
    // Load scraper status from GitHub Actions API
    loadScraperStatus()
  }, [])

  const loadScraperStatus = async () => {
    try {
      // In a real implementation, this would call GitHub Actions API
      // For now, we'll use the default groups
      setScraperGroups(defaultScraperGroups)
    } catch (error) {
      console.error('Failed to load scraper status:', error)
      setScraperGroups(defaultScraperGroups)
    } finally {
      setLoading(false)
    }
  }

  const triggerWorkflow = async (groupId: string) => {
    setTriggering(groupId)
    
    try {
      // Map group IDs to workflow file names
      const workflowMap: Record<string, string> = {
        'government-scrapers': 'main_scraper_workflow.yml',
        'state-ag-group-1': 'main_scraper_workflow.yml',
        'state-ag-group-2': 'main_scraper_workflow.yml',
        'state-ag-group-3': 'main_scraper_workflow.yml',
        'state-ag-group-4': 'main_scraper_workflow.yml',
        'news-and-api-scrapers': 'main_scraper_workflow.yml',
        'massachusetts-ag-frequent': 'massachusetts_ag.yml',
        'problematic-scrapers': 'main_scraper_workflow.yml'
      }

      const workflowFile = workflowMap[groupId]
      
      // This would trigger the GitHub Actions workflow
      // For demo purposes, we'll simulate the API call
      console.log(`Triggering workflow: ${workflowFile} for group: ${groupId}`)
      
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Update status
      setScraperGroups(prev => prev.map(group => 
        group.id === groupId 
          ? { ...group, status: 'running' as const, lastRun: new Date().toISOString() }
          : group
      ))
      
      // Simulate completion after 30 seconds
      setTimeout(() => {
        setScraperGroups(prev => prev.map(group => 
          group.id === groupId 
            ? { ...group, status: 'success' as const }
            : group
        ))
      }, 30000)
      
    } catch (error) {
      console.error('Failed to trigger workflow:', error)
      setScraperGroups(prev => prev.map(group => 
        group.id === groupId 
          ? { ...group, status: 'failed' as const }
          : group
      ))
    } finally {
      setTriggering(null)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-blue-100 text-blue-800'
      case 'success': return 'bg-green-100 text-green-800'
      case 'failed': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return '🔄'
      case 'success': return '✅'
      case 'failed': return '❌'
      default: return '⏸️'
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Scraper Control Center
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage and trigger breach data scrapers across 37+ sources
            </p>
          </div>
          <Button variant="outline" onClick={onClose}>
            ✕ Close
          </Button>
        </div>

        {/* Quick Actions */}
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">Quick Actions</h3>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => triggerWorkflow('all')}
              disabled={!!triggering}
            >
              🚀 Run All Scrapers
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('government-portals')}
              disabled={!!triggering}
            >
              🏢 Government Portals
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('state-ag-all')}
              disabled={!!triggering}
            >
              🏛️ All State AG Sites
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('rss-news-feeds')}
              disabled={!!triggering}
            >
              📰 RSS News Feeds
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('specialized-sites')}
              disabled={!!triggering}
            >
              🔍 Specialized Sites
            </Button>
          </div>
        </div>

        {/* Scraper Groups */}
        <div className="space-y-4">
          {scraperGroups.map(group => (
            <div key={group.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {group.name}
                  </h3>
                  <Badge className={getStatusColor(group.status)}>
                    {getStatusIcon(group.status)} {group.status}
                  </Badge>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => triggerWorkflow(group.id)}
                  disabled={!group.canTrigger || triggering === group.id || group.status === 'running'}
                >
                  {triggering === group.id ? '⏳ Starting...' : '▶️ Run Now'}
                </Button>
              </div>
              
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                {group.description}
              </p>
              
              <div className="flex flex-wrap gap-1 mb-2">
                {group.scrapers.map(scraper => (
                  <Badge key={scraper} variant="secondary" className="text-xs">
                    {scraper}
                  </Badge>
                ))}
              </div>
              
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                <span>Schedule: {group.schedule}</span>
                {group.lastRun && (
                  <span>Last run: {new Date(group.lastRun).toLocaleString()}</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Schedule Management */}
        <div className="mt-8 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
            📅 Schedule Management
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
            Current schedules are managed via GitHub Actions workflows. To modify schedules:
          </p>
          <div className="space-y-2 text-sm">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
              <span>Main workflow: Daily at 3 AM UTC (all scraper groups)</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span>Massachusetts AG: Every 6 hours (high frequency)</span>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => setShowScheduleManager(true)}
          >
            📝 Manage Schedules
          </Button>
        </div>

        {/* Schedule Manager Modal */}
        {showScheduleManager && (
          <ScheduleManager onClose={() => setShowScheduleManager(false)} />
        )}
      </div>
    </div>
  )
}

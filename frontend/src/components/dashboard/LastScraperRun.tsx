import React, { useState, useEffect } from 'react'
import { RefreshCw, Clock, CheckCircle, XCircle, AlertCircle, Play, ExternalLink } from 'lucide-react'
import { Button } from '../ui/Button'
import { githubActions } from '../../lib/github-actions'
import { formatRelativeTime } from '../../lib/utils'

interface WorkflowRun {
  id: number
  status: 'queued' | 'in_progress' | 'completed'
  conclusion: 'success' | 'failure' | 'cancelled' | 'skipped' | null
  created_at: string
  updated_at: string
}

interface LastScraperRunProps {
  className?: string
}

export function LastScraperRun({ className = '' }: LastScraperRunProps) {
  const [lastRun, setLastRun] = useState<WorkflowRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    loadLastRun()
    // Refresh every 5 minutes
    const interval = setInterval(loadLastRun, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const loadLastRun = async () => {
    try {
      setRefreshing(true)
      
      // Get the parallel scrapers workflow
      const workflows = await githubActions.getWorkflows()
      const parallelWorkflow = workflows.find(w => 
        w.name === 'Run All Scrapers (Parallel)' || 
        w.path.includes('paralell.yml')
      )

      if (parallelWorkflow) {
        const runs = await githubActions.getWorkflowRuns(parallelWorkflow.id, 1)
        if (runs.length > 0) {
          setLastRun(runs[0])
        }
      }
    } catch (error) {
      console.error('Failed to load last scraper run:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }



  const getStatusInfo = (run: WorkflowRun) => {
    if (run.status === 'in_progress') {
      return {
        icon: <Play className="w-4 h-4" />,
        text: 'Running',
        color: 'text-blue-600 dark:text-blue-400',
        bgColor: 'bg-blue-50 dark:bg-blue-900/20',
        borderColor: 'border-blue-200 dark:border-blue-800'
      }
    }

    if (run.status === 'queued') {
      return {
        icon: <Clock className="w-4 h-4" />,
        text: 'Queued',
        color: 'text-yellow-600 dark:text-yellow-400',
        bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
        borderColor: 'border-yellow-200 dark:border-yellow-800'
      }
    }

    if (run.conclusion === 'success') {
      return {
        icon: <CheckCircle className="w-4 h-4" />,
        text: 'Success',
        color: 'text-green-600 dark:text-green-400',
        bgColor: 'bg-green-50 dark:bg-green-900/20',
        borderColor: 'border-green-200 dark:border-green-800'
      }
    }

    if (run.conclusion === 'failure') {
      return {
        icon: <XCircle className="w-4 h-4" />,
        text: 'Failed',
        color: 'text-red-600 dark:text-red-400',
        bgColor: 'bg-red-50 dark:bg-red-900/20',
        borderColor: 'border-red-200 dark:border-red-800'
      }
    }

    return {
      icon: <AlertCircle className="w-4 h-4" />,
      text: 'Unknown',
      color: 'text-gray-600 dark:text-gray-400',
      bgColor: 'bg-gray-50 dark:bg-gray-900/20',
      borderColor: 'border-gray-200 dark:border-gray-800'
    }
  }

  if (loading) {
    return (
      <div className={`animate-pulse ${className}`}>
        <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gray-300 dark:bg-gray-600 rounded-lg"></div>
              <div>
                <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-24 mb-1"></div>
                <div className="h-3 bg-gray-300 dark:bg-gray-600 rounded w-16"></div>
              </div>
            </div>
            <div className="w-8 h-8 bg-gray-300 dark:bg-gray-600 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!lastRun) {
    return (
      <div className={`${className}`}>
        <div className="bg-gray-50 dark:bg-gray-900/20 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gray-300 dark:bg-gray-600 rounded-lg flex items-center justify-center">
                <Clock className="w-4 h-4 text-gray-500" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  No Recent Scraper Runs
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Waiting for data
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadLastRun}
              disabled={refreshing}
              className="w-8 h-8 p-0"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const statusInfo = getStatusInfo(lastRun)

  return (
    <div className={`${className}`}>
      <div className={`${statusInfo.bgColor} p-4 rounded-xl border ${statusInfo.borderColor} hover:shadow-lg transition-all duration-200`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-8 h-8 ${statusInfo.bgColor} rounded-lg flex items-center justify-center border ${statusInfo.borderColor}`}>
              <div className={statusInfo.color}>
                {statusInfo.icon}
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  Last Scraper Run
                </p>
                <span className={`px-2 py-0.5 ${statusInfo.bgColor} ${statusInfo.color} text-xs font-semibold rounded-full border ${statusInfo.borderColor}`}>
                  {statusInfo.text}
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {formatRelativeTime(lastRun.updated_at || lastRun.created_at)}
                {lastRun.status === 'in_progress' && ' • Currently running'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {lastRun.status === 'in_progress' && (
              <div className="flex space-x-1">
                <div className="w-1 h-1 bg-blue-500 rounded-full animate-pulse"></div>
                <div className="w-1 h-1 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-1 h-1 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
              </div>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={loadLastRun}
              disabled={refreshing}
              className="w-8 h-8 p-0"
              title="Refresh status"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

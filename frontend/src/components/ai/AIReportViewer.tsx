import React, { useState, useEffect } from 'react'
import { supabase } from '../../lib/supabase'
import { formatDate, formatAffectedCount } from '../../lib/utils'
import { 
  FileText, 
  Clock, 
  Search, 
  Globe, 
  Brain, 
  Download, 
  Share2, 
  AlertCircle,
  CheckCircle,
  ExternalLink,
  ArrowLeft
} from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'

interface AIReportViewerProps {
  reportId: string
  onClose?: () => void
}

interface ReportData {
  id: string
  status: string
  markdown_content: string
  processing_time_ms: number
  cost_estimate: number
  search_results_count: number
  scraped_urls_count: number
  ai_model_used: string
  created_at: string
  completed_at: string
  error_message?: string
  // Breach data
  organization_name: string
  affected_individuals: number | null
  source_name: string
  source_type: string
  breach_date: string | null
  reported_date: string | null
  what_was_leaked: string | null
}

export function AIReportViewer({ reportId, onClose }: AIReportViewerProps) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadReport()
  }, [reportId])

  const loadReport = async () => {
    try {
      setLoading(true)
      const { data, error } = await supabase
        .from('v_ai_reports')
        .select('*')
        .eq('id', reportId)
        .single()

      if (error) {
        throw new Error(error.message)
      }

      setReport(data)
    } catch (err) {
      console.error('Error loading report:', err)
      setError(err instanceof Error ? err.message : 'Failed to load report')
    } finally {
      setLoading(false)
    }
  }

  const downloadReport = () => {
    if (!report?.markdown_content) return

    const blob = new Blob([report.markdown_content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.organization_name}_breach_report.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const shareReport = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${report?.organization_name} Breach Report`,
          text: `AI-generated breach analysis for ${report?.organization_name}`,
          url: window.location.href
        })
      } catch (err) {
        console.log('Share cancelled')
      }
    } else {
      // Fallback: copy URL to clipboard
      navigator.clipboard.writeText(window.location.href)
      alert('Report URL copied to clipboard')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Brain className="w-12 h-12 mx-auto mb-4 text-blue-600 animate-pulse" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Loading AI Report
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Retrieving your breach analysis...
          </p>
        </div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-600" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Report Not Found
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            {error || 'The requested report could not be found.'}
          </p>
          {onClose && (
            <Button onClick={onClose} variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Go Back
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {onClose && (
                <Button variant="ghost" size="sm" onClick={onClose}>
                  <ArrowLeft className="w-4 h-4" />
                </Button>
              )}
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {report.organization_name} Breach Report
                </h1>
                <div className="flex items-center space-x-4 mt-1">
                  <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                    <Brain className="w-3 h-3 mr-1" />
                    AI Generated
                  </Badge>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {formatDate(report.completed_at || report.created_at)}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Button variant="outline" size="sm" onClick={downloadReport}>
                <Download className="w-4 h-4 mr-2" />
                Download
              </Button>
              <Button variant="outline" size="sm" onClick={shareReport}>
                <Share2 className="w-4 h-4 mr-2" />
                Share
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar with metadata */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 sticky top-24">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Report Details
              </h3>

              <div className="space-y-4">
                {/* Status */}
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Status</label>
                  <div className="flex items-center mt-1">
                    <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                    <span className="text-sm text-gray-900 dark:text-white capitalize">
                      {report.status}
                    </span>
                  </div>
                </div>

                {/* Processing Time */}
                {report.processing_time_ms && (
                  <div>
                    <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Processing Time</label>
                    <div className="flex items-center mt-1">
                      <Clock className="w-4 h-4 text-blue-600 mr-2" />
                      <span className="text-sm text-gray-900 dark:text-white">
                        {(report.processing_time_ms / 1000).toFixed(1)}s
                      </span>
                    </div>
                  </div>
                )}

                {/* Sources */}
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Sources Analyzed</label>
                  <div className="mt-1 space-y-1">
                    <div className="flex items-center">
                      <Search className="w-4 h-4 text-purple-600 mr-2" />
                      <span className="text-sm text-gray-900 dark:text-white">
                        {report.search_results_count} search results
                      </span>
                    </div>
                    <div className="flex items-center">
                      <Globe className="w-4 h-4 text-green-600 mr-2" />
                      <span className="text-sm text-gray-900 dark:text-white">
                        {report.scraped_urls_count} websites scraped
                      </span>
                    </div>
                  </div>
                </div>

                {/* AI Model */}
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400">AI Model</label>
                  <div className="flex items-center mt-1">
                    <Brain className="w-4 h-4 text-indigo-600 mr-2" />
                    <span className="text-sm text-gray-900 dark:text-white">
                      {report.ai_model_used}
                    </span>
                  </div>
                </div>

                {/* Breach Summary */}
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                    Breach Summary
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Affected:</span>
                      <span className="ml-2 font-medium text-gray-900 dark:text-white">
                        {formatAffectedCount(report.affected_individuals)}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Source:</span>
                      <span className="ml-2 text-gray-900 dark:text-white">
                        {report.source_name}
                      </span>
                    </div>
                    {report.breach_date && (
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Date:</span>
                        <span className="ml-2 text-gray-900 dark:text-white">
                          {formatDate(report.breach_date)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Main content */}
          <div className="lg:col-span-3">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <div className="p-6">
                <div className="prose prose-gray dark:prose-invert max-w-none">
                  {/* Render markdown content */}
                  <div 
                    className="markdown-content"
                    dangerouslySetInnerHTML={{ 
                      __html: report.markdown_content 
                        ? convertMarkdownToHTML(report.markdown_content)
                        : '<p>Report content is being processed...</p>'
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Simple markdown to HTML converter (you might want to use a proper library like marked)
function convertMarkdownToHTML(markdown: string): string {
  return markdown
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener noreferrer">$1 <ExternalLink className="inline w-3 h-3" /></a>')
    .replace(/\n/gim, '<br>')
}

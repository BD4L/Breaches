import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { supabase, type BreachRecord } from '../../lib/supabase'
import { Brain, MessageSquare, CheckCircle, Clock } from 'lucide-react'
import { StreamingAIReport } from './StreamingAIReport'

interface StreamingAIReportButtonProps {
  breach: BreachRecord
  className?: string
}

export function StreamingAIReportButton({ breach, className }: StreamingAIReportButtonProps) {
  const [showChat, setShowChat] = useState(false)
  const [hasExistingReport, setHasExistingReport] = useState(false)
  const [loading, setLoading] = useState(true)

  // Check for existing report on component mount
  useEffect(() => {
    checkExistingReport()
  }, [breach.id])

  const checkExistingReport = async () => {
    try {
      setLoading(true)
      const { data, error } = await supabase
        .from('research_jobs')
        .select('id, status, markdown_content')
        .eq('scraped_item', breach.id)
        .eq('report_type', 'ai_breach_analysis')
        .eq('status', 'completed')
        .not('markdown_content', 'is', null)
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (data && data.markdown_content) {
        setHasExistingReport(true)
      } else {
        setHasExistingReport(false)
      }
    } catch (err) {
      console.error('Error checking existing report:', err)
      setHasExistingReport(false)
    } finally {
      setLoading(false)
    }
  }

  const openExistingReport = async () => {
    try {
      // Get the report ID from research_jobs table
      const { data, error } = await supabase
        .from('research_jobs')
        .select('id')
        .eq('scraped_item', breach.id)
        .eq('report_type', 'ai_breach_analysis')
        .eq('status', 'completed')
        .not('markdown_content', 'is', null)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()

      if (data) {
        // Open existing report using the report ID
        const basePath = import.meta.env.BASE_URL || '/'
        const normalizedBasePath = basePath.replace(/\/$/, '') + '/'
        const reportUrl = `${normalizedBasePath}ai-report?id=${data.id}`
        window.open(reportUrl, '_blank')
      }
    } catch (err) {
      console.error('Error opening existing report:', err)
    }
  }

  const handleClick = () => {
    if (hasExistingReport) {
      openExistingReport()
    } else {
      setShowChat(true)
    }
  }

  const getButtonContent = () => {
    if (loading) {
      return (
        <>
          <Clock className="w-4 h-4 animate-spin" />
          <span>Checking...</span>
        </>
      )
    }

    if (hasExistingReport) {
      return (
        <>
          <CheckCircle className="w-4 h-4 text-green-600" />
          <span>View Report</span>
        </>
      )
    }

    return (
      <>
        <MessageSquare className="w-4 h-4" />
        <span>AI Chat Report</span>
      </>
    )
  }

  const getButtonVariant = () => {
    if (hasExistingReport) return 'default'
    return 'outline'
  }

  const getTooltipText = () => {
    if (loading) return 'Checking for existing report...'
    
    if (hasExistingReport) {
      return 'View existing AI-generated breach analysis report'
    }

    return 'Generate AI breach analysis with live streaming - see the research process in real-time'
  }

  return (
    <>
      <Button
        variant={getButtonVariant()}
        size="sm"
        onClick={handleClick}
        disabled={loading}
        className={`${className} flex items-center space-x-2 transition-all duration-200`}
        title={getTooltipText()}
      >
        {getButtonContent()}
      </Button>

      {/* Streaming Chat Modal */}
      {showChat && (
        <StreamingAIReport 
          breach={breach} 
          onClose={() => setShowChat(false)} 
        />
      )}
    </>
  )
}

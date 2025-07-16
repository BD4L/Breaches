import React, { useState, useRef, useEffect } from 'react'
import { Button } from '../ui/Button'
import { supabase, type BreachRecord } from '../../lib/supabase'
import { Brain, X, Send, Loader2, AlertCircle, CheckCircle } from 'lucide-react'

interface StreamingAIReportProps {
  breach: BreachRecord
  onClose: () => void
}

interface StreamMessage {
  type: 'status' | 'content' | 'complete' | 'error'
  message?: string
  content?: string
}

export function StreamingAIReport({ breach, onClose }: StreamingAIReportProps) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [messages, setMessages] = useState<StreamMessage[]>([])
  const [fullContent, setFullContent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startStreaming = async () => {
    setIsStreaming(true)
    setError(null)
    setMessages([])
    setFullContent('')

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController()

    try {
      // Get Supabase URL and anon key for the request
      const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL
      const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY

      const response = await fetch(`${supabaseUrl}/functions/v1/generate-ai-report-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${supabaseAnonKey}`,
          'apikey': supabaseAnonKey
        },
        body: JSON.stringify({
          breach_id: breach.id
        }),
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      // Process streaming response
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // Decode chunk
        const chunk = new TextDecoder().decode(value)
        buffer += chunk

        // Process complete lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (!data) continue

            try {
              const parsed: StreamMessage = JSON.parse(data)
              
              setMessages(prev => [...prev, parsed])

              // Accumulate content
              if (parsed.type === 'content' && parsed.content) {
                setFullContent(prev => prev + parsed.content)
              }

              // Handle completion
              if (parsed.type === 'complete') {
                setIsStreaming(false)
              }

              // Handle errors
              if (parsed.type === 'error') {
                setError(parsed.message || 'Unknown error occurred')
                setIsStreaming(false)
              }

            } catch (e) {
              console.warn('Failed to parse SSE data:', data)
            }
          }
        }
      }

    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Stream cancelled by user')
      } else {
        console.error('Streaming error:', err)
        setError(err instanceof Error ? err.message : 'Failed to generate report')
      }
      setIsStreaming(false)
    }
  }

  const cancelStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setIsStreaming(false)
  }

  const renderMessage = (msg: StreamMessage, index: number) => {
    switch (msg.type) {
      case 'status':
        return (
          <div key={index} className="flex items-center space-x-2 text-blue-600 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>{msg.message}</span>
          </div>
        )
      
      case 'content':
        return null // Content is rendered in the main content area
      
      case 'complete':
        return (
          <div key={index} className="flex items-center space-x-2 text-green-600 text-sm">
            <CheckCircle className="w-4 h-4" />
            <span>{msg.message}</span>
          </div>
        )
      
      case 'error':
        return (
          <div key={index} className="flex items-center space-x-2 text-red-600 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>{msg.message}</span>
          </div>
        )
      
      default:
        return null
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center space-x-3">
            <Brain className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-lg font-semibold">AI Breach Analysis</h2>
              <p className="text-sm text-gray-600">{breach.organization_name}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Status Messages */}
          <div className="space-y-2">
            {messages.map((msg, index) => renderMessage(msg, index))}
          </div>

          {/* Main Content Area */}
          {fullContent && (
            <div className="bg-gray-50 rounded-lg p-4 mt-4">
              <div className="prose prose-sm max-w-none">
                <div 
                  className="whitespace-pre-wrap"
                  dangerouslySetInnerHTML={{ 
                    __html: fullContent
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/\*(.*?)\*/g, '<em>$1</em>')
                      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline">$1</a>')
                      .replace(/\n/g, '<br>')
                  }}
                />
                {isStreaming && (
                  <span className="inline-block w-2 h-4 bg-blue-600 animate-pulse ml-1"></span>
                )}
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center space-x-2 text-red-700">
                <AlertCircle className="w-4 h-4" />
                <span className="font-medium">Error:</span>
                <span>{error}</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Footer */}
        <div className="border-t p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              {isStreaming ? 'Generating report...' : 'Ready to generate AI report'}
            </div>
            <div className="flex space-x-2">
              {isStreaming ? (
                <Button variant="outline" onClick={cancelStreaming}>
                  Cancel
                </Button>
              ) : (
                <Button onClick={startStreaming} disabled={!!fullContent}>
                  <Send className="w-4 h-4 mr-2" />
                  Generate Report
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

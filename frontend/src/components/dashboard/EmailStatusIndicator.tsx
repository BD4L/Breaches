import React, { useState, useEffect } from 'react'
import { Mail, CheckCircle, AlertCircle, Settings, Send } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { EmailPreferences } from '../preferences/EmailPreferences'
import { supabase } from '../../lib/supabase'

interface EmailStatus {
  email: string
  email_verified: boolean
  threshold: number
  isConfigured: boolean
}

export function EmailStatusIndicator() {
  const [emailStatus, setEmailStatus] = useState<EmailStatus>({
    email: '',
    email_verified: false,
    threshold: 0,
    isConfigured: false
  })
  const [loading, setLoading] = useState(true)
  const [sendingTest, setSendingTest] = useState(false)
  const [showEmailPreferences, setShowEmailPreferences] = useState(false)

  useEffect(() => {
    loadEmailStatus()
  }, [])

  const loadEmailStatus = async () => {
    try {
      setLoading(true)
      const { data, error } = await supabase
        .from('user_prefs')
        .select('email, email_verified, threshold')
        .eq('user_id', 'anonymous')
        .maybeSingle()

      if (error && error.code !== 'PGRST116') {
        throw error
      }

      if (data) {
        setEmailStatus({
          email: data.email || '',
          email_verified: data.email_verified || false,
          threshold: data.threshold || 0,
          isConfigured: !!(data.email && data.email_verified)
        })
      }
    } catch (error) {
      console.error('Error loading email status:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleEmailPreferencesClose = () => {
    setShowEmailPreferences(false)
    // Reload status after preferences are closed
    loadEmailStatus()
  }

  const sendQuickTestEmail = async () => {
    try {
      setSendingTest(true)

      // Call Supabase Edge Function to send test email
      const { data, error } = await supabase.functions.invoke('send-email-alert', {
        body: {
          type: 'test',
          email: emailStatus.email
        }
      })

      if (error) {
        throw new Error(error.message)
      }

      if (data?.success) {
        alert(`🎉 Test email sent successfully to ${emailStatus.email}! Check your inbox (and spam folder).`)
      } else {
        throw new Error(data?.error || 'Failed to send test email')
      }
    } catch (error) {
      console.error('Error sending test email:', error)
      alert(`Failed to send test email: ${error.message}. Please check your email configuration.`)
    } finally {
      setSendingTest(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-4 h-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600"></div>
        <span className="text-sm text-gray-500">Loading...</span>
      </div>
    )
  }

  return (
    <>
      <div className="flex items-center space-x-3">
        {emailStatus.isConfigured ? (
          <div className="flex items-center space-x-2">
            <Badge className="bg-green-100 text-green-800 border-green-200 flex items-center">
              <CheckCircle className="w-3 h-3 mr-1" />
              Email Alerts On
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={sendQuickTestEmail}
              disabled={sendingTest}
              className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-200"
              title="Send test email"
            >
              <Send className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowEmailPreferences(true)}
              className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
              title="Email settings"
            >
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center space-x-2">
            <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 flex items-center">
              <AlertCircle className="w-3 h-3 mr-1" />
              Setup Email Alerts
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowEmailPreferences(true)}
              className="flex items-center space-x-1 text-blue-600 border-blue-200 hover:bg-blue-50"
            >
              <Mail className="w-4 h-4" />
              <span>Setup</span>
            </Button>
          </div>
        )}
      </div>

      {showEmailPreferences && (
        <EmailPreferences onClose={handleEmailPreferencesClose} />
      )}
    </>
  )
}

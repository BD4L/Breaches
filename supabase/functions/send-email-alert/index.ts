import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface EmailRequest {
  type: 'test' | 'breach_alert'
  email?: string
  breachId?: number
  userId?: string
}

interface UserPreferences {
  email: string
  email_verified: boolean
  threshold: number
  alert_frequency: string
  email_format: string
  include_summary: boolean
  include_links: boolean
  max_alerts_per_day: number
  notify_high_impact: boolean
  notify_critical_sectors: boolean
  notify_local_breaches: boolean
  source_types: string[]
  keywords: string[]
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const resendApiKey = Deno.env.get('RESEND_API_KEY')!
    const fromEmail = Deno.env.get('ALERT_FROM_EMAIL') || 'alerts@yourdomain.com'
    const dashboardUrl = Deno.env.get('DASHBOARD_URL') || 'https://bd4l.github.io/Breaches/'

    if (!resendApiKey) {
      throw new Error('RESEND_API_KEY environment variable is required')
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Parse request
    const { type, email, breachId, userId }: EmailRequest = await req.json()

    console.log(`📧 Email request: type=${type}, email=${email}, breachId=${breachId}, userId=${userId}`)

    if (type === 'test') {
      // Send test email
      if (!email) {
        throw new Error('Email address is required for test emails')
      }

      const testEmailResult = await sendTestEmail(email, resendApiKey, fromEmail, dashboardUrl)
      
      return new Response(JSON.stringify({
        success: true,
        message: 'Test email sent successfully',
        messageId: testEmailResult.messageId
      }), {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      })

    } else if (type === 'breach_alert') {
      // Send breach alert
      if (!breachId || !userId) {
        throw new Error('breachId and userId are required for breach alerts')
      }

      const alertResult = await sendBreachAlert(breachId, userId, supabase, resendApiKey, fromEmail, dashboardUrl)
      
      return new Response(JSON.stringify({
        success: true,
        message: 'Breach alert processed',
        alertsSent: alertResult.alertsSent,
        errors: alertResult.errors
      }), {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      })

    } else {
      throw new Error('Invalid email type. Must be "test" or "breach_alert"')
    }

  } catch (error) {
    console.error('❌ Error in send-email-alert function:', error)
    
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }
})

async function sendTestEmail(email: string, resendApiKey: string, fromEmail: string, dashboardUrl: string) {
  const subject = '🛡️ Breach Alert Test - Your Email Notifications Are Working!'
  
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Breach Alert Test</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
            <h1 style="margin: 0; font-size: 28px;">🛡️ Test Email Successful!</h1>
            <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">Your breach alert notifications are configured correctly</p>
        </div>
        
        <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 25px;">
            <h2 style="color: #28a745; margin-top: 0;">✅ Email Setup Confirmed</h2>
            <p>Congratulations! Your email alert system is working properly. You will now receive notifications when new data breaches are detected that match your preferences.</p>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <h3 style="margin-top: 0; color: #495057;">What happens next?</h3>
                <ul style="margin: 0; padding-left: 20px;">
                    <li>Our system monitors for new breaches every 30 minutes</li>
                    <li>You'll receive alerts based on your configured preferences</li>
                    <li>Each email includes breach details, affected data, and source links</li>
                    <li>You can update your preferences anytime in the dashboard</li>
                </ul>
            </div>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="${dashboardUrl}" style="background: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">View Dashboard</a>
        </div>
        
        <div style="border-top: 1px solid #dee2e6; padding-top: 20px; font-size: 14px; color: #6c757d; text-align: center;">
            <p>You're receiving this test email because you configured breach alerts in the dashboard.</p>
            <p><a href="${dashboardUrl}" style="color: #007bff;">Manage preferences</a> | <a href="${dashboardUrl}" style="color: #007bff;">View dashboard</a></p>
        </div>
    </body>
    </html>
  `

  const textContent = `
🛡️ BREACH ALERT TEST - EMAIL NOTIFICATIONS WORKING!

✅ Email Setup Confirmed

Congratulations! Your email alert system is working properly. You will now receive notifications when new data breaches are detected that match your preferences.

What happens next?
• Our system monitors for new breaches every 30 minutes
• You'll receive alerts based on your configured preferences  
• Each email includes breach details, affected data, and source links
• You can update your preferences anytime in the dashboard

View Dashboard: ${dashboardUrl}

---
You're receiving this test email because you configured breach alerts in the dashboard.
Manage preferences: ${dashboardUrl}
  `

  return await sendEmailViaResend(email, subject, htmlContent, textContent, resendApiKey, fromEmail)
}

async function sendBreachAlert(breachId: number, userId: string, supabase: any, resendApiKey: string, fromEmail: string, dashboardUrl: string) {
  // Get breach details
  const { data: breach, error: breachError } = await supabase
    .from('v_breach_dashboard')
    .select('*')
    .eq('id', breachId)
    .single()

  if (breachError || !breach) {
    throw new Error(`Breach not found: ${breachError?.message}`)
  }

  // Get user preferences
  const { data: userPrefs, error: prefsError } = await supabase
    .from('user_prefs')
    .select('*')
    .eq('user_id', userId)
    .single()

  if (prefsError || !userPrefs) {
    throw new Error(`User preferences not found: ${prefsError?.message}`)
  }

  if (!userPrefs.email_verified) {
    throw new Error('User email not verified')
  }

  // Check if breach matches user preferences
  if (!breachMatchesPreferences(breach, userPrefs)) {
    return { alertsSent: 0, errors: 0, message: 'Breach does not match user preferences' }
  }

  // Create breach alert email content
  const emailContent = createBreachAlertEmail(breach, userPrefs, dashboardUrl)

  // Send email
  const result = await sendEmailViaResend(
    userPrefs.email,
    emailContent.subject,
    emailContent.html,
    emailContent.text,
    resendApiKey,
    fromEmail
  )

  return { alertsSent: 1, errors: 0, messageId: result.messageId }
}

function breachMatchesPreferences(breach: any, prefs: UserPreferences): boolean {
  // Check threshold
  if (prefs.threshold > 0 && (breach.affected_individuals || 0) < prefs.threshold) {
    return false
  }

  // Check source types
  if (prefs.source_types.length > 0 && !prefs.source_types.includes(breach.source_type)) {
    return false
  }

  // Check keywords
  if (prefs.keywords.length > 0) {
    const searchText = `${breach.organization_name} ${breach.what_was_leaked || ''}`.toLowerCase()
    const hasKeyword = prefs.keywords.some(keyword => 
      searchText.includes(keyword.toLowerCase())
    )
    if (!hasKeyword) {
      return false
    }
  }

  return true
}

function createBreachAlertEmail(breach: any, prefs: UserPreferences, dashboardUrl: string) {
  const subject = `🚨 Data Breach Alert: ${breach.organization_name} (${formatNumber(breach.affected_individuals)} affected)`
  
  // HTML and text content would be similar to the Python script
  // For brevity, I'll create a simplified version here
  const html = `
    <h1>🚨 Data Breach Alert</h1>
    <h2>${breach.organization_name}</h2>
    <p><strong>Affected Individuals:</strong> ${formatNumber(breach.affected_individuals)}</p>
    <p><strong>Breach Date:</strong> ${breach.breach_date || 'Unknown'}</p>
    <p><strong>What Was Leaked:</strong> ${breach.what_was_leaked || 'Not specified'}</p>
    <p><a href="${dashboardUrl}">View Full Details</a></p>
  `
  
  const text = `
🚨 DATA BREACH ALERT

${breach.organization_name}
Affected Individuals: ${formatNumber(breach.affected_individuals)}
Breach Date: ${breach.breach_date || 'Unknown'}
What Was Leaked: ${breach.what_was_leaked || 'Not specified'}

View Full Details: ${dashboardUrl}
  `

  return { subject, html, text }
}

async function sendEmailViaResend(email: string, subject: string, html: string, text: string, resendApiKey: string, fromEmail: string) {
  const response = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${resendApiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from: fromEmail,
      to: [email],
      subject,
      html,
      text,
      tags: [
        { name: 'category', value: 'breach-alert' },
        { name: 'source', value: 'frontend' }
      ]
    })
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to send email: ${response.status} - ${error}`)
  }

  const result = await response.json()
  console.log(`✅ Email sent successfully to ${email}, Message ID: ${result.id}`)
  
  return { messageId: result.id }
}

function formatNumber(num: number | null | undefined): string {
  if (!num) return 'Unknown'
  return num.toLocaleString()
}

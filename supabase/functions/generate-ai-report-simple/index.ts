import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Content-Type': 'application/json'
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: corsHeaders
    })
  }

  try {
    console.log('🚀 AI Report function called')
    
    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if (!supabaseUrl || !supabaseServiceKey) {
      console.error('❌ Missing Supabase configuration')
      return new Response(JSON.stringify({
        error: 'Missing Supabase configuration',
        details: 'SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set'
      }), {
        status: 500,
        headers: corsHeaders
      })
    }
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey)
    console.log('✅ Supabase client initialized')
    
    // Parse request
    let breachId, userId
    try {
      const body = await req.json()
      breachId = body.breachId
      userId = body.userId
      console.log(`📋 Request parsed - breachId: ${breachId}, userId: ${userId}`)
    } catch (error) {
      console.error('❌ Invalid JSON in request body:', error)
      return new Response(JSON.stringify({
        error: 'Invalid JSON in request body',
        details: error.message
      }), {
        status: 400,
        headers: corsHeaders
      })
    }
    
    if (!breachId) {
      console.error('❌ breachId is required')
      return new Response(JSON.stringify({
        error: 'breachId is required',
        details: 'Please provide a valid breachId in the request body'
      }), {
        status: 400,
        headers: corsHeaders
      })
    }
    
    console.log(`🤖 Starting AI report generation for breach ${breachId}`)
    
    // Check API key availability
    const apiKeys = {
      gemini: !!Deno.env.get('GEMINI_API_KEY'),
      anthropic: !!Deno.env.get('ANTHROPIC_API_KEY'),
      brave_search: !!Deno.env.get('BRAVE_SEARCH_API_KEY'),
      firecrawl: !!Deno.env.get('FIRECRAWL_API_KEY')
    }
    
    console.log('🔑 API Keys availability:', apiKeys)
    
    if (!apiKeys.gemini && !apiKeys.anthropic) {
      console.error('❌ No AI API keys configured')
      return new Response(JSON.stringify({
        error: 'No AI API keys configured',
        details: 'Please set GEMINI_API_KEY or ANTHROPIC_API_KEY in Supabase Edge Function environment variables.',
        apiKeysStatus: apiKeys
      }), {
        status: 500,
        headers: corsHeaders
      })
    }

    // Get breach data
    const { data: breach, error: breachError } = await supabase
      .from('v_breach_dashboard')
      .select('*')
      .eq('id', breachId)
      .single()
      
    if (breachError || !breach) {
      console.error('❌ Breach not found:', breachError)
      return new Response(JSON.stringify({
        error: 'Breach not found',
        details: breachError?.message || 'No breach found with the provided ID'
      }), {
        status: 404,
        headers: corsHeaders
      })
    }

    console.log(`📊 Found breach: ${breach.organization_name}`)

    // Check if report already exists
    const { data: existingReport } = await supabase
      .from('research_jobs')
      .select('id, status, markdown_content')
      .eq('scraped_item', breachId)
      .eq('report_type', 'ai_breach_analysis')
      .maybeSingle()
      
    if (existingReport && existingReport.status === 'completed') {
      console.log(`📋 Returning existing report for breach ${breachId}`)
      return new Response(JSON.stringify({
        reportId: existingReport.id,
        status: 'completed',
        cached: true,
        message: 'Report already exists and is completed'
      }), {
        status: 200,
        headers: corsHeaders
      })
    }
    
    if (existingReport && existingReport.status === 'processing') {
      console.log(`⏳ Report already processing for breach ${breachId}`)
      return new Response(JSON.stringify({
        reportId: existingReport.id,
        status: 'processing',
        message: 'Report generation in progress. Please check back in a few moments.'
      }), {
        status: 200,
        headers: corsHeaders
      })
    }

    // Create new report record
    const { data: reportRecord, error: reportError } = await supabase
      .from('research_jobs')
      .insert({
        scraped_item: breachId,
        status: 'processing',
        report_type: 'ai_breach_analysis',
        requested_by: userId || null,
        ai_model_used: 'gemini-2.5-flash',
        created_at: new Date().toISOString(),
        metadata: {
          breach_data: breach,
          api_keys_available: apiKeys
        }
      })
      .select()
      .single()
      
    if (reportError) {
      console.error('❌ Failed to create report record:', reportError)
      return new Response(JSON.stringify({
        error: 'Failed to create report record',
        details: reportError.message
      }), {
        status: 500,
        headers: corsHeaders
      })
    }

    console.log(`📊 Created report record ${reportRecord.id}`)

    // Return immediate response - processing will happen in background
    return new Response(JSON.stringify({
      reportId: reportRecord.id,
      status: 'processing',
      message: 'AI report generation started. This may take 2-3 minutes to complete.',
      breachOrganization: breach.organization_name,
      apiKeysAvailable: apiKeys
    }), {
      status: 200,
      headers: corsHeaders
    })

  } catch (error) {
    console.error('❌ Error in AI report function:', error)
    
    return new Response(JSON.stringify({
      error: error.message || 'Unknown error occurred',
      details: error.stack || 'No stack trace available',
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: corsHeaders
    })
  }
})

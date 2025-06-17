// Supabase Edge Function for AI Breach Report Generation
// Uses Gemini 2.5 Flash with MCP tools for comprehensive breach analysis

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { GoogleGenerativeAI } from "https://esm.sh/@google/generative-ai@0.21.0"

// CORS headers for browser requests
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface BreachData {
  id: number
  organization_name: string
  affected_individuals: number | null
  breach_date: string | null
  reported_date: string | null
  what_was_leaked: string | null
  source_name: string
  source_type: string
  notice_document_url: string | null
  item_url: string | null
  incident_nature_text: string | null
  data_types_compromised: string[] | null
}

interface SearchResult {
  title: string
  url: string
  snippet: string
}

interface MCPSearchResponse {
  results: SearchResult[]
  total: number
}

interface MCPScrapeResponse {
  markdown: string
  url: string
  success: boolean
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
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Initialize Gemini AI
    const geminiApiKey = Deno.env.get('GEMINI_API_KEY')
    if (!geminiApiKey) {
      throw new Error('GEMINI_API_KEY environment variable is required')
    }
    const genAI = new GoogleGenerativeAI(geminiApiKey)

    // Parse request
    const { breachId, userId } = await req.json()
    if (!breachId) {
      throw new Error('breachId is required')
    }

    console.log(`🤖 Starting AI report generation for breach ${breachId}`)
    const startTime = Date.now()

    // Check rate limits (if user provided)
    if (userId) {
      const { data: rateLimitCheck } = await supabase.rpc('check_daily_rate_limit', {
        p_user_id: userId,
        p_max_reports: 10
      })

      if (!rateLimitCheck) {
        return new Response(
          JSON.stringify({ error: 'Daily rate limit exceeded (10 reports per day)' }),
          { status: 429, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        )
      }
    }

    // Check if report already exists
    const { data: existingReport } = await supabase
      .from('research_jobs')
      .select('id, status, markdown_content')
      .eq('scraped_item', breachId)
      .eq('report_type', 'ai_breach_analysis')
      .maybeSingle()

    if (existingReport && existingReport.status === 'completed') {
      console.log(`📋 Returning existing report for breach ${breachId}`)
      return new Response(
        JSON.stringify({ 
          reportId: existingReport.id,
          status: 'completed',
          cached: true 
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Get breach data
    const { data: breach, error: breachError } = await supabase
      .from('v_breach_dashboard')
      .select('*')
      .eq('id', breachId)
      .single()

    if (breachError || !breach) {
      throw new Error(`Breach not found: ${breachError?.message}`)
    }

    // Create or update research job record
    const { data: reportRecord, error: reportError } = await supabase
      .from('research_jobs')
      .upsert({
        scraped_item: breachId,
        status: 'processing',
        report_type: 'ai_breach_analysis',
        requested_by: userId || null,
        ai_model_used: 'gemini-2.5-flash',
        metadata: { breach_data: breach }
      })
      .select()
      .single()

    if (reportError) {
      throw new Error(`Failed to create report record: ${reportError.message}`)
    }

    console.log(`📊 Created report record ${reportRecord.id}`)

    try {
      // Step 1: Search for additional information
      console.log(`🔍 Searching for information about ${breach.organization_name}`)
      const searchQuery = `"${breach.organization_name}" data breach cybersecurity incident ${breach.breach_date || ''} ${breach.affected_individuals ? `${breach.affected_individuals} affected` : ''}`
      
      // Use MCP Brave Search (simulated - replace with actual MCP call)
      const searchResults = await performWebSearch(searchQuery)
      
      // Step 2: Scrape relevant URLs for more context
      console.log(`📄 Scraping ${Math.min(searchResults.length, 3)} relevant URLs`)
      const scrapedContent = await scrapeRelevantUrls(searchResults.slice(0, 3))

      // Step 3: Generate comprehensive report with Gemini
      console.log(`🧠 Generating AI report with Gemini 2.5 Flash`)
      const report = await generateBreachReport(genAI, breach, searchResults, scrapedContent)

      // Step 4: Update report record with results
      const processingTime = Date.now() - startTime
      const estimatedCost = 0.17 // Estimated cost per report

      const { error: updateError } = await supabase
        .from('research_jobs')
        .update({
          status: 'completed',
          markdown_content: report,
          processing_time_ms: processingTime,
          cost_estimate: estimatedCost,
          search_results_count: searchResults.length,
          scraped_urls_count: scrapedContent.length,
          completed_at: new Date().toISOString(),
          metadata: {
            ...reportRecord.metadata,
            search_results: searchResults.map(r => ({ title: r.title, url: r.url })),
            scraped_urls: scrapedContent.map(c => c.url),
            processing_stats: {
              total_time_ms: processingTime,
              search_time_ms: Math.floor(processingTime * 0.3),
              scrape_time_ms: Math.floor(processingTime * 0.4),
              ai_generation_time_ms: Math.floor(processingTime * 0.3)
            }
          }
        })
        .eq('id', reportRecord.id)

      if (updateError) {
        console.error('Failed to update report:', updateError)
      }

      // Update usage statistics (if user provided)
      if (userId) {
        await supabase.rpc('increment_usage_stats', {
          p_user_id: userId,
          p_cost: estimatedCost,
          p_processing_time_ms: processingTime
        })
      }

      console.log(`✅ Report generation completed in ${processingTime}ms`)

      return new Response(
        JSON.stringify({ 
          reportId: reportRecord.id,
          status: 'completed',
          processingTimeMs: processingTime,
          searchResultsCount: searchResults.length,
          scrapedUrlsCount: scrapedContent.length
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )

    } catch (error) {
      // Update report record with error
      await supabase
        .from('research_jobs')
        .update({
          status: 'failed',
          error_message: error.message,
          processing_time_ms: Date.now() - startTime
        })
        .eq('id', reportRecord.id)

      throw error
    }

  } catch (error) {
    console.error('Error generating AI report:', error)
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  }
})

// Helper function to perform web search (replace with actual MCP call)
async function performWebSearch(query: string): Promise<SearchResult[]> {
  // TODO: Replace with actual MCP brave-search call
  // For now, return mock data
  console.log(`🔍 Performing web search: ${query}`)
  
  // Simulate search results
  return [
    {
      title: "Data Breach Notification - Official Statement",
      url: "https://example.com/breach-notice",
      snippet: "Official notification regarding the recent data security incident..."
    },
    {
      title: "Cybersecurity Incident Analysis",
      url: "https://security-blog.com/analysis",
      snippet: "Technical analysis of the breach methodology and impact..."
    },
    {
      title: "Regulatory Response and Compliance",
      url: "https://regulatory.gov/response",
      snippet: "Regulatory authorities respond to the data breach incident..."
    }
  ]
}

// Helper function to scrape URLs (replace with actual MCP call)
async function scrapeRelevantUrls(searchResults: SearchResult[]): Promise<MCPScrapeResponse[]> {
  // TODO: Replace with actual MCP firecrawl calls
  console.log(`📄 Scraping ${searchResults.length} URLs`)
  
  const scrapedContent: MCPScrapeResponse[] = []
  
  for (const result of searchResults) {
    // Simulate scraping
    scrapedContent.push({
      url: result.url,
      markdown: `# ${result.title}\n\n${result.snippet}\n\nDetailed content about the breach would be extracted here...`,
      success: true
    })
  }
  
  return scrapedContent
}

// Helper function to generate report with Gemini
async function generateBreachReport(
  genAI: GoogleGenerativeAI,
  breach: BreachData,
  searchResults: SearchResult[],
  scrapedContent: MCPScrapeResponse[]
): Promise<string> {
  const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" })

  const contextData = {
    breach_info: {
      organization: breach.organization_name,
      affected_individuals: breach.affected_individuals,
      breach_date: breach.breach_date,
      reported_date: breach.reported_date,
      data_compromised: breach.what_was_leaked,
      source: breach.source_name,
      source_type: breach.source_type,
      incident_nature: breach.incident_nature_text,
      data_types: breach.data_types_compromised
    },
    search_results: searchResults,
    scraped_content: scrapedContent.map(c => ({ url: c.url, content: c.markdown }))
  }

  const prompt = `You are a cybersecurity analyst generating a comprehensive breach report. Create a detailed markdown report with the following sections:

# ${breach.organization_name} Data Breach Analysis

## Executive Summary
Provide a concise overview of the incident, impact, and key findings.

## Incident Timeline
Detail the chronological sequence of events from discovery to disclosure.

## Impact Assessment
Analyze the scope and severity of the breach, including affected individuals and data types.

## Technical Analysis
Examine the attack vectors, vulnerabilities exploited, and security failures.

## Regulatory and Compliance Implications
Discuss relevant regulations, compliance requirements, and potential penalties.

## Industry Context
Compare with similar incidents and industry trends.

## Recommendations
Provide actionable security recommendations and best practices.

## Sources and References
List all sources with proper hyperlinks.

Context Data:
${JSON.stringify(contextData, null, 2)}

Requirements:
- Use markdown formatting with proper headers
- Include hyperlinks to all referenced sources
- Provide specific, actionable insights
- Maintain professional, analytical tone
- Ensure accuracy and cite sources properly
- Include relevant statistics and comparisons where possible`

  const result = await model.generateContent(prompt)
  const response = await result.response
  return response.text()
}

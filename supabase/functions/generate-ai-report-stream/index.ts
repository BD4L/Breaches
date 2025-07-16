import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

// Simple prompt function
function buildKimiPrompt(organizationName: string): string {
  return `Conduct MULTIPLE targeted web searches to thoroughly research the ${organizationName} data breach. Do separate searches for different aspects:

SEARCH 1: Basic breach information
- Search: "${organizationName} data breach 2024 2025"
- Search: "${organizationName} cybersecurity incident"

SEARCH 2: Official government sources  
- Search: "${organizationName} SEC filing 8-K cybersecurity"
- Search: "${organizationName} HHS breach report"
- Search: "${organizationName} attorney general notification"

SEARCH 3: News and media coverage
- Search: "${organizationName} breach news Reuters Bloomberg"
- Search: "${organizationName} cybersecurity KrebsOnSecurity BleepingComputer"

SEARCH 4: Legal developments
- Search: "${organizationName} class action lawsuit breach"
- Search: "${organizationName} settlement fine penalty"

SEARCH 5: Company and customer demographics
- Search: "${organizationName} customer demographics target market"
- Search: "${organizationName} user base statistics"

SEARCH 6: Breach notifications and response
- Search: "${organizationName} breach notification letter"
- Search: "${organizationName} credit monitoring offer"

For each search, find:
- Exact number of people affected
- What specific data was stolen/leaked  
- Timeline of events
- Company's response and notifications
- Legal consequences
- Customer demographics for marketing targeting

Compile all findings into a comprehensive report with direct links to sources. Use clear headings and organize logically.`;
}

// OpenRouter configuration for Kimi-K2 with web search
function getOpenRouterConfig() {
  return {
    model: 'moonshotai/kimi-k2:online',
    stream: true, // Enable streaming
    plugins: [
      {
        id: 'web',
        max_results: 50,
        search_prompt: 'Conduct multiple targeted web searches to gather comprehensive information. Search different aspects separately for better results. Use all search results to create a thorough breach analysis report. Cite all sources as clickable markdown links like [Source Name](https://example.com).'
      }
    ]
  }
}

serve(async (req) => {
  // Handle CORS
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
      }
    })
  }

  try {
    console.log('🚀 AI Report Streaming function called')
    
    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if (!supabaseUrl || !supabaseServiceKey) {
      console.error('❌ Missing Supabase configuration')
      return new Response('Missing Supabase configuration', { status: 500 })
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Parse request
    const { breach_id } = await req.json()
    
    if (!breach_id) {
      return new Response('Missing breach_id', { status: 400 })
    }

    console.log('📊 Processing breach ID:', breach_id)

    // Get breach data
    const { data: breach, error: breachError } = await supabase
      .from('breach_raw')
      .select('*')
      .eq('id', breach_id)
      .single()

    if (breachError || !breach) {
      console.error('❌ Breach not found:', breachError)
      return new Response('Breach not found', { status: 404 })
    }

    // Get API key
    const OPENROUTER_KEY = Deno.env.get('OPENROUTER_API_KEY')
    if (!OPENROUTER_KEY) {
      console.error('❌ Missing OpenRouter API key')
      return new Response('Missing API configuration', { status: 500 })
    }

    console.log('🤖 Starting AI report generation for:', breach.organization_name)

    // Create streaming response
    const stream = new ReadableStream({
      async start(controller) {
        try {
          // Send initial status
          controller.enqueue(`data: {"type": "status", "message": "🔍 Starting research on ${breach.organization_name} breach..."}\n\n`)

          const config = getOpenRouterConfig()
          const prompt = buildKimiPrompt(breach.organization_name)

          // Make streaming request to OpenRouter
          const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${OPENROUTER_KEY}`,
              'Content-Type': 'application/json',
              'HTTP-Referer': 'https://breachdash.com',
              'X-Title': 'Breach Dashboard AI Reports'
            },
            body: JSON.stringify({
              ...config,
              messages: [
                {
                  role: 'user',
                  content: prompt
                }
              ]
            })
          })

          if (!response.ok) {
            throw new Error(`OpenRouter API error: ${response.status}`)
          }

          // Process streaming response
          const reader = response.body?.getReader()
          if (!reader) {
            throw new Error('No response body')
          }

          let buffer = ''
          let fullContent = ''

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
                const data = line.slice(6)
                if (data === '[DONE]') {
                  continue
                }

                try {
                  const parsed = JSON.parse(data)
                  const content = parsed.choices?.[0]?.delta?.content
                  
                  if (content) {
                    fullContent += content
                    // Send content chunk to client
                    controller.enqueue(`data: {"type": "content", "content": ${JSON.stringify(content)}}\n\n`)
                  }
                } catch (e) {
                  // Skip invalid JSON
                  continue
                }
              }
            }
          }

          // Save complete report to database
          const { error: saveError } = await supabase
            .from('research_jobs')
            .insert({
              scraped_item: breach_id,
              status: 'completed',
              report_type: 'ai_breach_analysis',
              markdown_content: fullContent,
              ai_model_used: 'kimi-k2',
              completed_at: new Date().toISOString()
            })

          if (saveError) {
            console.error('❌ Error saving report:', saveError)
          }

          // Send completion status
          controller.enqueue(`data: {"type": "complete", "message": "✅ Report generation complete!"}\n\n`)
          controller.close()

        } catch (error) {
          console.error('❌ Streaming error:', error)
          controller.enqueue(`data: {"type": "error", "message": "Error: ${error.message}"}\n\n`)
          controller.close()
        }
      }
    })

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
      }
    })

  } catch (error) {
    console.error('❌ Function error:', error)
    return new Response(`Error: ${error.message}`, { 
      status: 500,
      headers: {
        'Access-Control-Allow-Origin': '*'
      }
    })
  }
})

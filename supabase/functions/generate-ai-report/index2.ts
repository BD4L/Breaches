// Minimal AI report generator using Kimi-K2 (OpenRouter)
// This function purposefully avoids any extra prompt scaffolding.
// It sends ONE plain-English prompt to Kimi and stores the markdown result.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const OPENROUTER_KEY = Deno.env.get('OPENROUTER_API_KEY') || ''
if (!OPENROUTER_KEY) {
  console.warn('OPENROUTER_API_KEY is not set – function will return 500')
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Content-Type': 'application/json'
}

// Very simple citation extractor so we can count sources in the UI
function extractMarkdownLinks(md: string): { title: string; url: string }[] {
  const re = /\[([^\]]+)\]\((https?:[^)]+)\)/g
  const out: { title: string; url: string }[] = []
  let m
  while ((m = re.exec(md)) !== null) {
    out.push({ title: m[1], url: m[2] })
  }
  return out
}

function buildPrompt(org: string): string {
  return `search the web for information on this ${org} databreach pull from sources that are reputable and any news sources you can find, sources from government sites etc find pdfs with information. Find out what the company that experienced the databreaches target demographic is so we can target the people affected in marketing strategy. Find out exact numbers (people affected), what was leaked, when, if they have sent out an email/notification yet etc. Link all sources

Ensure the company is the one i asked for`
}

async function runKimi(messages: any[]) {
  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${OPENROUTER_KEY}`,
      'HTTP-Referer': 'localhost',
      'X-Title': 'simple-breach-report'
    },
    body: JSON.stringify({
      model: 'moonshotai/kimi-k2',
      messages,
      max_tokens: 4096,
      temperature: 0.7
    })
  })
  if (!res.ok) throw new Error(`OpenRouter error ${res.status}`)
  const data = await res.json()
  return data.choices?.[0]?.message?.content ?? ''
}

serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders })

  try {
    if (!OPENROUTER_KEY) throw new Error('OPENROUTER_API_KEY not configured')

    const { breachId, userId } = await req.json()
    if (!breachId) throw new Error('breachId is required')

    const supabaseUrl = Deno.env.get('SUPABASE_URL')
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
    if (!supabaseUrl || !supabaseServiceKey) throw new Error('Supabase env missing')

    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Fetch breach row
    const { data: breach, error: bErr } = await supabase.from('v_breach_dashboard').select('id, organization_name').eq('id', breachId).single()
    if (bErr || !breach) throw new Error('Breach not found')

    // Start job record
    const { data: job } = await supabase.from('research_jobs').insert({
      scraped_item: breachId,
      status: 'processing',
      report_type: 'ai_breach_analysis_simple',
      requested_by: userId || null,
      ai_model_used: 'moonshotai/kimi-k2'
    }).select().single()

    // Build prompt & run Kimi
    const prompt = buildPrompt(breach.organization_name)
    const markdown = await runKimi([
      { role: 'system', content: 'You are an expert cybersecurity analyst.' },
      { role: 'user', content: prompt }
    ])

    const links = extractMarkdownLinks(markdown)
    const finished = await supabase.from('research_jobs').update({
      status: 'completed',
      markdown_content: markdown,
      search_results_count: links.length,
      scraped_urls_count: links.length,
      completed_at: new Date().toISOString(),
      metadata: {
        research_method: 'kimi-simple',
        links
      }
    }).eq('id', job.id)

    return new Response(JSON.stringify({ reportId: job.id, status: 'completed', links: links.length }), { headers: corsHeaders })
  } catch (err) {
    console.error(err)
    return new Response(JSON.stringify({ error: err.message || err }), { status: 500, headers: corsHeaders })
  }
}) 
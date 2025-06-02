// GitHub Actions API integration for scraper management
// Note: This requires a GitHub Personal Access Token with workflow permissions

interface WorkflowRun {
  id: number
  name: string
  status: 'queued' | 'in_progress' | 'completed'
  conclusion: 'success' | 'failure' | 'cancelled' | 'skipped' | null
  created_at: string
  updated_at: string
  workflow_id: number
}

interface Workflow {
  id: number
  name: string
  path: string
  state: 'active' | 'deleted'
  created_at: string
  updated_at: string
}

class GitHubActionsAPI {
  private owner = 'HackerManMarlin'
  private repo = 'Breaches'
  private baseUrl = 'https://api.github.com'
  
  // Note: In production, this should be handled server-side for security
  private getHeaders() {
    const token = import.meta.env.PUBLIC_GITHUB_TOKEN
    if (!token) {
      throw new Error('GitHub token not configured')
    }
    
    return {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json'
    }
  }

  async getWorkflows(): Promise<Workflow[]> {
    try {
      const response = await fetch(
        `${this.baseUrl}/repos/${this.owner}/${this.repo}/actions/workflows`,
        { headers: this.getHeaders() }
      )
      
      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status}`)
      }
      
      const data = await response.json()
      return data.workflows
    } catch (error) {
      console.error('Failed to fetch workflows:', error)
      return []
    }
  }

  async getWorkflowRuns(workflowId: number, limit = 10): Promise<WorkflowRun[]> {
    try {
      const response = await fetch(
        `${this.baseUrl}/repos/${this.owner}/${this.repo}/actions/workflows/${workflowId}/runs?per_page=${limit}`,
        { headers: this.getHeaders() }
      )
      
      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status}`)
      }
      
      const data = await response.json()
      return data.workflow_runs
    } catch (error) {
      console.error('Failed to fetch workflow runs:', error)
      return []
    }
  }

  async triggerWorkflow(workflowId: number, ref = 'frontend', inputs?: Record<string, any>): Promise<boolean> {
    try {
      const response = await fetch(
        `${this.baseUrl}/repos/${this.owner}/${this.repo}/actions/workflows/${workflowId}/dispatches`,
        {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify({
            ref,
            inputs: inputs || {}
          })
        }
      )
      
      return response.ok
    } catch (error) {
      console.error('Failed to trigger workflow:', error)
      return false
    }
  }

  async triggerWorkflowByName(workflowName: string, inputs?: Record<string, any>): Promise<boolean> {
    try {
      const workflows = await this.getWorkflows()
      const workflow = workflows.find(w => w.name === workflowName || w.path.includes(workflowName))
      
      if (!workflow) {
        throw new Error(`Workflow not found: ${workflowName}`)
      }
      
      return this.triggerWorkflow(workflow.id, 'frontend', inputs)
    } catch (error) {
      console.error('Failed to trigger workflow by name:', error)
      return false
    }
  }

  // Predefined workflow triggers for your scraper groups
  async triggerMainScraperWorkflow(): Promise<boolean> {
    return this.triggerWorkflowByName('main_scraper_workflow.yml')
  }

  async triggerMassachusettsAG(options?: {
    filterDaysBack?: string
    processingMode?: 'BASIC' | 'ENHANCED' | 'FULL'
    forceProcess?: boolean
  }): Promise<boolean> {
    return this.triggerWorkflowByName('massachusetts_ag.yml', {
      filter_days_back: options?.filterDaysBack || '7',
      processing_mode: options?.processingMode || 'ENHANCED',
      force_process: options?.forceProcess?.toString() || 'true'
    })
  }

  async triggerCaliforniaAG(): Promise<boolean> {
    return this.triggerWorkflowByName('cali.yml')
  }

  // Get status of all scraper-related workflows
  async getScraperStatus(): Promise<{
    workflow: string
    status: string
    lastRun?: string
    conclusion?: string
  }[]> {
    try {
      const workflows = await this.getWorkflows()
      const scraperWorkflows = workflows.filter(w => 
        w.name.toLowerCase().includes('scraper') || 
        w.name.toLowerCase().includes('ag') ||
        w.path.includes('scraper') ||
        w.path.includes('ag')
      )

      const statusPromises = scraperWorkflows.map(async workflow => {
        const runs = await this.getWorkflowRuns(workflow.id, 1)
        const lastRun = runs[0]
        
        return {
          workflow: workflow.name,
          status: lastRun?.status || 'unknown',
          lastRun: lastRun?.created_at,
          conclusion: lastRun?.conclusion || undefined
        }
      })

      return Promise.all(statusPromises)
    } catch (error) {
      console.error('Failed to get scraper status:', error)
      return []
    }
  }
}

export const githubActions = new GitHubActionsAPI()

// Workflow mapping for the UI
export const WORKFLOW_GROUPS = {
  'government-scrapers': {
    name: 'Government & Federal Scrapers',
    workflow: 'main_scraper_workflow.yml',
    description: 'SEC EDGAR 8-K, HHS OCR',
    scrapers: ['SEC EDGAR 8-K', 'HHS OCR']
  },
  'state-ag-group-1': {
    name: 'State AG Group 1',
    workflow: 'main_scraper_workflow.yml',
    description: 'Delaware, California, Washington, Hawaii',
    scrapers: ['Delaware AG', 'California AG', 'Washington AG', 'Hawaii AG']
  },
  'state-ag-group-2': {
    name: 'State AG Group 2',
    workflow: 'main_scraper_workflow.yml',
    description: 'Indiana, Iowa, Maine',
    scrapers: ['Indiana AG', 'Iowa AG', 'Maine AG']
  },
  'state-ag-group-3': {
    name: 'State AG Group 3',
    workflow: 'main_scraper_workflow.yml',
    description: 'Massachusetts, Montana',
    scrapers: ['Massachusetts AG', 'Montana AG']
  },
  'state-ag-group-4': {
    name: 'State AG Group 4',
    workflow: 'main_scraper_workflow.yml',
    description: 'North Dakota, Oklahoma, Vermont, Wisconsin, Texas',
    scrapers: ['North Dakota AG', 'Oklahoma Cyber', 'Vermont AG', 'Wisconsin DATCP', 'Texas AG']
  },
  'news-and-api-scrapers': {
    name: 'News & API Scrapers',
    workflow: 'main_scraper_workflow.yml',
    description: 'BreachSense, Cybersecurity News, Company IR, HIBP API',
    scrapers: ['BreachSense', 'Cybersecurity News RSS', 'Company IR', 'HIBP API']
  },
  'massachusetts-ag-frequent': {
    name: 'Massachusetts AG (Frequent)',
    workflow: 'massachusetts_ag.yml',
    description: 'High-frequency Massachusetts AG scraper',
    scrapers: ['Massachusetts AG'],
    schedule: 'Every 6 hours'
  },
  'california-ag-special': {
    name: 'California AG (Special)',
    workflow: 'cali.yml',
    description: 'California AG with enhanced PDF processing',
    scrapers: ['California AG']
  }
} as const

export type WorkflowGroupId = keyof typeof WORKFLOW_GROUPS

import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { AlertCircle, CheckCircle, Settings, RefreshCw } from 'lucide-react'
import { githubActions } from '../../lib/github-actions'

interface GitHubTokenDebugProps {
  onClose: () => void
}

interface ValidationResult {
  valid: boolean
  error?: string
  workflows?: string[]
}

export function GitHubTokenDebug({ onClose }: GitHubTokenDebugProps) {
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [tokenInfo, setTokenInfo] = useState<{
    exists: boolean
    format: string
    preview: string
  } | null>(null)

  useEffect(() => {
    checkTokenInfo()
    validateSetup()
  }, [])

  const checkTokenInfo = () => {
    const token = import.meta.env.PUBLIC_GITHUB_TOKEN
    if (token) {
      setTokenInfo({
        exists: true,
        format: token.startsWith('ghp_') ? 'Classic Token' : 
                token.startsWith('github_pat_') ? 'Fine-grained Token' : 'Unknown Format',
        preview: `${token.substring(0, 8)}...${token.substring(token.length - 4)}`
      })
    } else {
      setTokenInfo({
        exists: false,
        format: 'Not Found',
        preview: 'N/A'
      })
    }
  }

  const validateSetup = async () => {
    setLoading(true)
    try {
      const result = await githubActions.validateSetup()
      setValidation(result)
    } catch (error) {
      setValidation({
        valid: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    } finally {
      setLoading(false)
    }
  }

  const testWorkflowTrigger = async () => {
    setLoading(true)
    try {
      // Try to trigger a simple workflow
      const success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
        run_government: 'false',
        run_state_ag_1: 'false',
        run_state_ag_2: 'false',
        run_state_ag_3: 'false',
        run_state_ag_4: 'false',
        run_news_api: 'false',
        run_problematic: 'false'
      })
      
      if (success) {
        alert('✅ Test workflow trigger successful!')
      } else {
        alert('❌ Test workflow trigger failed')
      }
    } catch (error) {
      alert(`❌ Test failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <Settings className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              GitHub Token Debug
            </h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Token Information */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Token Configuration
            </h3>
            
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Token Exists:
                </span>
                <Badge className={tokenInfo?.exists ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                  {tokenInfo?.exists ? (
                    <>
                      <CheckCircle className="w-3 h-3 mr-1" />
                      Yes
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3 h-3 mr-1" />
                      No
                    </>
                  )}
                </Badge>
              </div>

              {tokenInfo?.exists && (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Token Format:
                    </span>
                    <Badge className="bg-blue-100 text-blue-800">
                      {tokenInfo.format}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Token Preview:
                    </span>
                    <code className="text-sm bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded">
                      {tokenInfo.preview}
                    </code>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Validation Results */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                API Validation
              </h3>
              <Button
                variant="outline"
                size="sm"
                onClick={validateSetup}
                disabled={loading}
                className="flex items-center space-x-2"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                <span>Retest</span>
              </Button>
            </div>

            {validation && (
              <div className={`p-4 rounded-lg border ${
                validation.valid 
                  ? 'bg-green-50 border-green-200 text-green-800' 
                  : 'bg-red-50 border-red-200 text-red-800'
              }`}>
                <div className="flex items-center space-x-2 mb-2">
                  {validation.valid ? (
                    <CheckCircle className="w-5 h-5" />
                  ) : (
                    <AlertCircle className="w-5 h-5" />
                  )}
                  <span className="font-medium">
                    {validation.valid ? 'GitHub API Access: Success' : 'GitHub API Access: Failed'}
                  </span>
                </div>

                {validation.error && (
                  <p className="text-sm mb-3">{validation.error}</p>
                )}

                {validation.workflows && validation.workflows.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">
                      Available Workflows ({validation.workflows.length}):
                    </p>
                    <div className="space-y-1">
                      {validation.workflows.map((workflow, index) => (
                        <div key={index} className="text-xs bg-white bg-opacity-50 px-2 py-1 rounded">
                          {workflow}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Setup Instructions */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Setup Instructions
            </h3>
            
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">
                If token is missing or invalid:
              </h4>
              <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
                <li>Go to <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer" className="underline">GitHub Settings → Tokens</a></li>
                <li>Create new token with <strong>repo</strong> and <strong>workflow</strong> scopes</li>
                <li>Copy the token (starts with ghp_)</li>
                <li>Add to <a href="https://github.com/HackerManMarlin/Breaches/settings/secrets/actions" target="_blank" rel="noopener noreferrer" className="underline">Repository Secrets</a> as <strong>PUBLIC_GITHUB_TOKEN</strong></li>
                <li>Redeploy the frontend</li>
              </ol>
            </div>
          </div>

          {/* Test Actions */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Test Actions
            </h3>
            
            <div className="flex space-x-3">
              <Button
                onClick={testWorkflowTrigger}
                disabled={loading || !validation?.valid}
                className="flex items-center space-x-2"
              >
                <span>🧪</span>
                <span>Test Workflow Trigger</span>
              </Button>
              
              <Button
                variant="outline"
                onClick={() => window.open('https://github.com/HackerManMarlin/Breaches/actions', '_blank')}
              >
                <span>📊</span>
                <span>View GitHub Actions</span>
              </Button>
            </div>
          </div>

          {/* Environment Info */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Environment Info
            </h3>
            
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="font-medium">Repository:</span>
                  <div className="text-gray-600 dark:text-gray-400">HackerManMarlin/Breaches</div>
                </div>
                <div>
                  <span className="font-medium">Branch:</span>
                  <div className="text-gray-600 dark:text-gray-400">main</div>
                </div>
                <div>
                  <span className="font-medium">API Base:</span>
                  <div className="text-gray-600 dark:text-gray-400">api.github.com</div>
                </div>
                <div>
                  <span className="font-medium">Environment:</span>
                  <div className="text-gray-600 dark:text-gray-400">GitHub Pages</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end p-6 border-t border-gray-200 dark:border-gray-700">
          <Button onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}

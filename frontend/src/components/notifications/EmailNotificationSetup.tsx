import React, { useState, useEffect } from 'react'
import { Mail, Bell, Settings, Save, X, Plus, Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

interface NotificationRule {
  id: string
  name: string
  email: string
  minAffected: number
  sourceTypes: string[]
  keywords: string[]
  enabled: boolean
  frequency: 'immediate' | 'daily' | 'weekly'
}

interface EmailNotificationSetupProps {
  isOpen: boolean
  onClose: () => void
}

export function EmailNotificationSetup({ isOpen, onClose }: EmailNotificationSetupProps) {
  const [rules, setRules] = useState<NotificationRule[]>([])
  const [editingRule, setEditingRule] = useState<NotificationRule | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  useEffect(() => {
    if (isOpen) {
      loadNotificationRules()
    }
  }, [isOpen])

  const loadNotificationRules = () => {
    // Load from localStorage for now (in production, this would be from the database)
    const saved = localStorage.getItem('breach-notification-rules')
    if (saved) {
      setRules(JSON.parse(saved))
    } else {
      // Default rule
      setRules([
        {
          id: '1',
          name: 'High Impact Breaches',
          email: '',
          minAffected: 10000,
          sourceTypes: ['State AG Sites', 'Government Portals'],
          keywords: ['ransomware', 'healthcare', 'financial'],
          enabled: false,
          frequency: 'immediate'
        }
      ])
    }
  }

  const saveRules = (newRules: NotificationRule[]) => {
    setRules(newRules)
    localStorage.setItem('breach-notification-rules', JSON.stringify(newRules))
  }

  const createNewRule = () => {
    const newRule: NotificationRule = {
      id: Date.now().toString(),
      name: 'New Alert Rule',
      email: '',
      minAffected: 1000,
      sourceTypes: ['State AG Sites'],
      keywords: [],
      enabled: false,
      frequency: 'immediate'
    }
    setEditingRule(newRule)
    setIsCreating(true)
  }

  const saveRule = (rule: NotificationRule) => {
    if (isCreating) {
      saveRules([...rules, rule])
      setIsCreating(false)
    } else {
      saveRules(rules.map(r => r.id === rule.id ? rule : r))
    }
    setEditingRule(null)
  }

  const deleteRule = (id: string) => {
    saveRules(rules.filter(r => r.id !== id))
  }

  const toggleRule = (id: string) => {
    saveRules(rules.map(r => 
      r.id === id ? { ...r, enabled: !r.enabled } : r
    ))
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
              <Mail className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">Email Notifications</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Get notified when breaches match your criteria
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* Current Rules */}
          <div className="space-y-4 mb-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Notification Rules</h3>
              <Button onClick={createNewRule} className="flex items-center space-x-2">
                <Plus className="w-4 h-4" />
                <span>Add Rule</span>
              </Button>
            </div>

            {rules.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                <Bell className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No notification rules configured</p>
                <p className="text-sm">Create your first rule to get started</p>
              </div>
            ) : (
              <div className="space-y-3">
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    className={`p-4 rounded-lg border transition-all ${
                      rule.enabled
                        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                        : 'bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h4 className="font-medium text-gray-900 dark:text-white">{rule.name}</h4>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            rule.enabled
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                              : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                          }`}>
                            {rule.enabled ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                          <p><strong>Email:</strong> {rule.email || 'Not configured'}</p>
                          <p><strong>Min Affected:</strong> {rule.minAffected.toLocaleString()}+ people</p>
                          <p><strong>Sources:</strong> {rule.sourceTypes.join(', ')}</p>
                          {rule.keywords.length > 0 && (
                            <p><strong>Keywords:</strong> {rule.keywords.join(', ')}</p>
                          )}
                          <p><strong>Frequency:</strong> {rule.frequency}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => toggleRule(rule.id)}
                          className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                            rule.enabled
                              ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-900/50'
                              : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50'
                          }`}
                        >
                          {rule.enabled ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          onClick={() => setEditingRule(rule)}
                          className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                        >
                          <Settings className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteRule(rule.id)}
                          className="p-2 text-red-400 hover:text-red-600 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Edit Rule Modal */}
          {editingRule && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-60 p-4">
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
                <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {isCreating ? 'Create' : 'Edit'} Notification Rule
                  </h3>
                  <button
                    onClick={() => {
                      setEditingRule(null)
                      setIsCreating(false)
                    }}
                    className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="p-6 overflow-y-auto max-h-[calc(80vh-140px)]">
                  <div className="space-y-4">
                    {/* Rule Name */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Rule Name
                      </label>
                      <Input
                        value={editingRule.name}
                        onChange={(e) => setEditingRule({ ...editingRule, name: e.target.value })}
                        placeholder="e.g., High Impact Healthcare Breaches"
                      />
                    </div>

                    {/* Email */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Email Address
                      </label>
                      <Input
                        type="email"
                        value={editingRule.email}
                        onChange={(e) => setEditingRule({ ...editingRule, email: e.target.value })}
                        placeholder="your-email@example.com"
                      />
                    </div>

                    {/* Minimum Affected */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Minimum People Affected
                      </label>
                      <Input
                        type="number"
                        value={editingRule.minAffected}
                        onChange={(e) => setEditingRule({ ...editingRule, minAffected: parseInt(e.target.value) || 0 })}
                        placeholder="1000"
                      />
                    </div>

                    {/* Source Types */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Source Types
                      </label>
                      <div className="space-y-2">
                        {['State AG Sites', 'Government Portals', 'Specialized Breach Sites'].map((type) => (
                          <label key={type} className="flex items-center">
                            <input
                              type="checkbox"
                              checked={editingRule.sourceTypes.includes(type)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setEditingRule({
                                    ...editingRule,
                                    sourceTypes: [...editingRule.sourceTypes, type]
                                  })
                                } else {
                                  setEditingRule({
                                    ...editingRule,
                                    sourceTypes: editingRule.sourceTypes.filter(t => t !== type)
                                  })
                                }
                              }}
                              className="mr-2"
                            />
                            <span className="text-sm text-gray-700 dark:text-gray-300">{type}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    {/* Keywords */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Keywords (comma-separated)
                      </label>
                      <Input
                        value={editingRule.keywords.join(', ')}
                        onChange={(e) => setEditingRule({
                          ...editingRule,
                          keywords: e.target.value.split(',').map(k => k.trim()).filter(Boolean)
                        })}
                        placeholder="ransomware, healthcare, financial"
                      />
                    </div>

                    {/* Frequency */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Notification Frequency
                      </label>
                      <select
                        value={editingRule.frequency}
                        onChange={(e) => setEditingRule({
                          ...editingRule,
                          frequency: e.target.value as 'immediate' | 'daily' | 'weekly'
                        })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      >
                        <option value="immediate">Immediate</option>
                        <option value="daily">Daily Digest</option>
                        <option value="weekly">Weekly Summary</option>
                      </select>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEditingRule(null)
                      setIsCreating(false)
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => saveRule(editingRule)}
                    disabled={!editingRule.email || !editingRule.name}
                    className="flex items-center space-x-2"
                  >
                    <Save className="w-4 h-4" />
                    <span>Save Rule</span>
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Info Section */}
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
            <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">How Email Notifications Work</h4>
            <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
              <li>• Notifications are sent when new breaches match your criteria</li>
              <li>• Immediate notifications are sent within minutes of discovery</li>
              <li>• Daily/weekly digests summarize all matching breaches</li>
              <li>• You can have multiple rules with different criteria</li>
              <li>• Rules can be enabled/disabled at any time</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
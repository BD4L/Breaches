import React, { useState, useEffect } from 'react'
import { X, Calendar, User, Tag, FileText, AlertTriangle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import type { BreachRecord } from '../../lib/supabase'
import type { SaveBreachData } from './SaveBreachButton'

interface SaveBreachModalProps {
  breach: BreachRecord
  onSave: (data: SaveBreachData) => Promise<void>
  onClose: () => void
  isLoading: boolean
}

export function SaveBreachModal({ breach, onSave, onClose, isLoading }: SaveBreachModalProps) {
  const [formData, setFormData] = useState<SaveBreachData>({
    collection_name: 'Default',
    priority_level: 'medium',
    notes: '',
    tags: [],
    review_status: 'pending',
    assigned_to: '',
    due_date: ''
  })
  const [newTag, setNewTag] = useState('')

  // Auto-suggest priority based on breach data
  useEffect(() => {
    let suggestedPriority: SaveBreachData['priority_level'] = 'medium'
    
    if (breach.affected_individuals) {
      if (breach.affected_individuals > 100000) {
        suggestedPriority = 'critical'
      } else if (breach.affected_individuals > 10000) {
        suggestedPriority = 'high'
      } else if (breach.affected_individuals > 1000) {
        suggestedPriority = 'medium'
      } else {
        suggestedPriority = 'low'
      }
    }

    // Check for high-risk data types
    const highRiskTypes = ['ssn', 'social security', 'credit card', 'financial', 'medical', 'health']
    const dataTypes = (breach.data_types_compromised || []).join(' ').toLowerCase()
    const hasHighRiskData = highRiskTypes.some(type => dataTypes.includes(type))
    
    if (hasHighRiskData && suggestedPriority === 'low') {
      suggestedPriority = 'medium'
    }

    setFormData(prev => ({ ...prev, priority_level: suggestedPriority }))
  }, [breach])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSave(formData)
  }

  const addTag = () => {
    if (newTag.trim() && !formData.tags?.includes(newTag.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...(prev.tags || []), newTag.trim()]
      }))
      setNewTag('')
    }
  }

  const removeTag = (tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags?.filter(tag => tag !== tagToRemove) || []
    }))
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag()
    }
  }

  const priorityOptions = [
    { value: 'low', label: 'Low', color: 'text-green-600' },
    { value: 'medium', label: 'Medium', color: 'text-yellow-600' },
    { value: 'high', label: 'High', color: 'text-orange-600' },
    { value: 'critical', label: 'Critical', color: 'text-red-600' }
  ]

  const statusOptions = [
    { value: 'pending', label: 'Pending Review' },
    { value: 'in_progress', label: 'In Progress' },
    { value: 'reviewed', label: 'Reviewed' },
    { value: 'escalated', label: 'Escalated' },
    { value: 'closed', label: 'Closed' }
  ]

  const collections = [
    'Default',
    'High Priority',
    'Legal Review',
    'Customer Impact',
    'Regulatory Compliance',
    'Technical Analysis'
  ]

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Save Breach for Review
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {breach.organization_name}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Collection Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Collection
            </label>
            <select
              value={formData.collection_name}
              onChange={(e) => setFormData(prev => ({ ...prev, collection_name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              {collections.map(collection => (
                <option key={collection} value={collection}>
                  {collection}
                </option>
              ))}
            </select>
          </div>

          {/* Priority Level */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Priority Level
            </label>
            <div className="grid grid-cols-2 gap-2">
              {priorityOptions.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, priority_level: option.value as any }))}
                  className={`
                    p-3 rounded-md border text-left transition-colors
                    ${formData.priority_level === option.value
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }
                  `}
                >
                  <div className="flex items-center">
                    <AlertTriangle className={`w-4 h-4 mr-2 ${option.color}`} />
                    <span className="font-medium">{option.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Review Status */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Review Status
            </label>
            <select
              value={formData.review_status}
              onChange={(e) => setFormData(prev => ({ ...prev, review_status: e.target.value as any }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              {statusOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* Assigned To */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <User className="w-4 h-4 inline mr-1" />
              Assigned To
            </label>
            <Input
              type="text"
              value={formData.assigned_to}
              onChange={(e) => setFormData(prev => ({ ...prev, assigned_to: e.target.value }))}
              placeholder="Enter assignee name or email"
            />
          </div>

          {/* Due Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Calendar className="w-4 h-4 inline mr-1" />
              Due Date
            </label>
            <Input
              type="date"
              value={formData.due_date}
              onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
            />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Tag className="w-4 h-4 inline mr-1" />
              Tags
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {formData.tags?.map(tag => (
                <Badge
                  key={tag}
                  className="bg-blue-100 text-blue-800 border-blue-200 cursor-pointer hover:bg-blue-200"
                  onClick={() => removeTag(tag)}
                >
                  {tag} ×
                </Badge>
              ))}
            </div>
            <div className="flex space-x-2">
              <Input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Add a tag..."
                className="flex-1"
              />
              <Button type="button" onClick={addTag} variant="outline" size="sm">
                Add
              </Button>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <FileText className="w-4 h-4 inline mr-1" />
              Notes
            </label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
              placeholder="Add any notes about this breach..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-gray-700">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Saving...' : 'Save Breach'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

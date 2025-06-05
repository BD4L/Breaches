import React, { useState, useEffect } from 'react'
import { 
  Bookmark, 
  Filter, 
  Search, 
  Calendar, 
  User, 
  Tag, 
  AlertCircle,
  FileText,
  Download,
  Trash2,
  Edit3
} from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { BreachDetail } from '../breach/BreachDetail'
import { getSavedBreaches, removeSavedBreach, updateSavedBreach } from '../../lib/supabase'
import type { SavedBreachRecord } from '../../lib/supabase'

interface SavedBreachesViewProps {
  onClose?: () => void
}

export function SavedBreachesView({ onClose }: SavedBreachesViewProps) {
  const [savedBreaches, setSavedBreaches] = useState<SavedBreachRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCollection, setSelectedCollection] = useState('all')
  const [selectedPriority, setSelectedPriority] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [expandedBreach, setExpandedBreach] = useState<number | null>(null)

  useEffect(() => {
    loadSavedBreaches()
  }, [])

  const loadSavedBreaches = async () => {
    try {
      setLoading(true)
      const result = await getSavedBreaches()
      if (result.data) {
        setSavedBreaches(result.data)
      }
    } catch (error) {
      console.error('Failed to load saved breaches:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRemove = async (savedId: number) => {
    try {
      await removeSavedBreach(savedId)
      setSavedBreaches(prev => prev.filter(breach => breach.saved_id !== savedId))
    } catch (error) {
      console.error('Failed to remove saved breach:', error)
    }
  }

  const handleStatusUpdate = async (savedId: number, newStatus: string) => {
    try {
      await updateSavedBreach(savedId, { review_status: newStatus })
      setSavedBreaches(prev => prev.map(breach => 
        breach.saved_id === savedId 
          ? { ...breach, review_status: newStatus }
          : breach
      ))
    } catch (error) {
      console.error('Failed to update breach status:', error)
    }
  }

  // Filter saved breaches
  const filteredBreaches = savedBreaches.filter(breach => {
    const matchesSearch = !searchTerm || 
      breach.organization_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      breach.notes?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      breach.tags?.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))

    const matchesCollection = selectedCollection === 'all' || breach.collection_name === selectedCollection
    const matchesPriority = selectedPriority === 'all' || breach.priority_level === selectedPriority
    const matchesStatus = selectedStatus === 'all' || breach.review_status === selectedStatus

    return matchesSearch && matchesCollection && matchesPriority && matchesStatus
  })

  // Get unique values for filters
  const collections = [...new Set(savedBreaches.map(b => b.collection_name))]
  const priorities = ['low', 'medium', 'high', 'critical']
  const statuses = ['pending', 'in_progress', 'reviewed', 'escalated', 'closed']

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200'
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'low': return 'bg-green-100 text-green-800 border-green-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'in_progress': return 'bg-purple-100 text-purple-800 border-purple-200'
      case 'reviewed': return 'bg-green-100 text-green-800 border-green-200'
      case 'escalated': return 'bg-red-100 text-red-800 border-red-200'
      case 'closed': return 'bg-gray-100 text-gray-800 border-gray-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const exportSavedBreaches = () => {
    const csvContent = [
      ['Organization', 'Collection', 'Priority', 'Status', 'Assigned To', 'Due Date', 'Notes', 'Tags', 'Saved Date'].join(','),
      ...filteredBreaches.map(breach => [
        breach.organization_name || '',
        breach.collection_name || '',
        breach.priority_level || '',
        breach.review_status || '',
        breach.assigned_to || '',
        breach.due_date || '',
        (breach.notes || '').replace(/,/g, ';'),
        (breach.tags || []).join(';'),
        new Date(breach.saved_at).toLocaleDateString()
      ].join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `saved-breaches-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-600 dark:text-gray-400">Loading saved breaches...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Bookmark className="w-6 h-6 text-blue-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Saved Breaches
          </h1>
          <Badge className="bg-blue-100 text-blue-800 border-blue-200">
            {filteredBreaches.length} of {savedBreaches.length}
          </Badge>
        </div>
        <div className="flex items-center space-x-2">
          <Button onClick={exportSavedBreaches} variant="outline" size="sm">
            <Download className="w-4 h-4 mr-1" />
            Export
          </Button>
          {onClose && (
            <Button onClick={onClose} variant="outline" size="sm">
              Close
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Search */}
          <div className="lg:col-span-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search breaches, notes, tags..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {/* Collection Filter */}
          <div>
            <select
              value={selectedCollection}
              onChange={(e) => setSelectedCollection(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
            >
              <option value="all">All Collections</option>
              {collections.map(collection => (
                <option key={collection} value={collection}>
                  {collection}
                </option>
              ))}
            </select>
          </div>

          {/* Priority Filter */}
          <div>
            <select
              value={selectedPriority}
              onChange={(e) => setSelectedPriority(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
            >
              <option value="all">All Priorities</option>
              {priorities.map(priority => (
                <option key={priority} value={priority}>
                  {priority.charAt(0).toUpperCase() + priority.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
            >
              <option value="all">All Statuses</option>
              {statuses.map(status => (
                <option key={status} value={status}>
                  {status.replace('_', ' ').charAt(0).toUpperCase() + status.replace('_', ' ').slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Saved Breaches List */}
      <div className="space-y-4">
        {filteredBreaches.length === 0 ? (
          <div className="text-center py-12">
            <Bookmark className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No saved breaches found
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {savedBreaches.length === 0 
                ? "Start saving breaches for review and tracking."
                : "Try adjusting your filters to see more results."
              }
            </p>
          </div>
        ) : (
          filteredBreaches.map(breach => (
            <div
              key={breach.saved_id}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6"
            >
              {/* Breach Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    {breach.organization_name}
                  </h3>
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <Badge className={getPriorityColor(breach.priority_level)}>
                      <AlertCircle className="w-3 h-3 mr-1" />
                      {breach.priority_level}
                    </Badge>
                    <Badge className={getStatusColor(breach.review_status)}>
                      {breach.review_status.replace('_', ' ')}
                    </Badge>
                    {breach.collection_name !== 'Default' && (
                      <Badge className="bg-purple-100 text-purple-800 border-purple-200">
                        <Tag className="w-3 h-3 mr-1" />
                        {breach.collection_name}
                      </Badge>
                    )}
                    {breach.tags?.map(tag => (
                      <Badge key={tag} className="bg-gray-100 text-gray-800 border-gray-200">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center text-sm text-gray-600 dark:text-gray-400 space-x-4">
                    <span>Saved: {new Date(breach.saved_at).toLocaleDateString()}</span>
                    {breach.assigned_to && (
                      <span className="flex items-center">
                        <User className="w-3 h-3 mr-1" />
                        {breach.assigned_to}
                      </span>
                    )}
                    {breach.due_date && (
                      <span className="flex items-center">
                        <Calendar className="w-3 h-3 mr-1" />
                        Due: {new Date(breach.due_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpandedBreach(
                      expandedBreach === breach.id ? null : breach.id
                    )}
                  >
                    {expandedBreach === breach.id ? 'Hide Details' : 'Show Details'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemove(breach.saved_id)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Notes */}
              {breach.notes && (
                <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-md">
                  <div className="flex items-start">
                    <FileText className="w-4 h-4 text-gray-500 mt-0.5 mr-2 flex-shrink-0" />
                    <p className="text-sm text-gray-700 dark:text-gray-300">{breach.notes}</p>
                  </div>
                </div>
              )}

              {/* Status Update */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-600 dark:text-gray-400">Status:</span>
                  <select
                    value={breach.review_status}
                    onChange={(e) => handleStatusUpdate(breach.saved_id, e.target.value)}
                    className="text-sm px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    {statuses.map(status => (
                      <option key={status} value={status}>
                        {status.replace('_', ' ').charAt(0).toUpperCase() + status.replace('_', ' ').slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="text-sm text-gray-500">
                  {breach.affected_individuals && (
                    <span>{breach.affected_individuals.toLocaleString()} affected</span>
                  )}
                </div>
              </div>

              {/* Expanded Details */}
              {expandedBreach === breach.id && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <BreachDetail breach={breach} />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

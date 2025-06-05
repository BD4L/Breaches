import React, { useState } from 'react'
import { Bookmark, BookmarkCheck, Plus, Tag, AlertCircle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { SaveBreachModal } from './SaveBreachModal'
import type { BreachRecord } from '../../lib/supabase'

interface SaveBreachButtonProps {
  breach: BreachRecord
  isSaved?: boolean
  savedData?: {
    collection_name: string
    priority_level: string
    review_status: string
  }
  onSave?: (breachId: number, data: SaveBreachData) => Promise<void>
  onRemove?: (breachId: number) => Promise<void>
  className?: string
}

export interface SaveBreachData {
  collection_name: string
  priority_level: 'low' | 'medium' | 'high' | 'critical'
  notes?: string
  tags?: string[]
  review_status: 'pending' | 'in_progress' | 'reviewed' | 'escalated' | 'closed'
  assigned_to?: string
  due_date?: string
}

export function SaveBreachButton({ 
  breach, 
  isSaved = false, 
  savedData,
  onSave, 
  onRemove,
  className = '' 
}: SaveBreachButtonProps) {
  const [showModal, setShowModal] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const handleQuickSave = async () => {
    if (isSaved && onRemove) {
      setIsLoading(true)
      try {
        await onRemove(breach.id)
      } catch (error) {
        console.error('Failed to remove saved breach:', error)
      } finally {
        setIsLoading(false)
      }
    } else {
      setShowModal(true)
    }
  }

  const handleSaveWithDetails = async (data: SaveBreachData) => {
    if (!onSave) return
    
    setIsLoading(true)
    try {
      await onSave(breach.id, data)
      setShowModal(false)
    } catch (error) {
      console.error('Failed to save breach:', error)
    } finally {
      setIsLoading(false)
    }
  }

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

  return (
    <>
      <div className={`flex items-center space-x-2 ${className}`}>
        <Button
          variant={isSaved ? "default" : "ghost"}
          size="sm"
          onClick={handleQuickSave}
          disabled={isLoading}
          className={`
            ${isSaved 
              ? 'bg-blue-600 hover:bg-blue-700 text-white' 
              : 'hover:bg-blue-50 text-blue-600 border-blue-200'
            }
          `}
        >
          {isSaved ? (
            <BookmarkCheck className="w-4 h-4 mr-1" />
          ) : (
            <Bookmark className="w-4 h-4 mr-1" />
          )}
          {isSaved ? 'Saved' : 'Save'}
        </Button>

        {!isSaved && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowModal(true)}
            className="text-gray-600 hover:text-gray-800"
          >
            <Plus className="w-4 h-4" />
          </Button>
        )}

        {isSaved && savedData && (
          <div className="flex items-center space-x-1">
            <Badge className={getPriorityColor(savedData.priority_level)}>
              <AlertCircle className="w-3 h-3 mr-1" />
              {savedData.priority_level}
            </Badge>
            <Badge className={getStatusColor(savedData.review_status)}>
              {savedData.review_status}
            </Badge>
            {savedData.collection_name !== 'Default' && (
              <Badge className="bg-purple-100 text-purple-800 border-purple-200">
                <Tag className="w-3 h-3 mr-1" />
                {savedData.collection_name}
              </Badge>
            )}
          </div>
        )}
      </div>

      {showModal && (
        <SaveBreachModal
          breach={breach}
          onSave={handleSaveWithDetails}
          onClose={() => setShowModal(false)}
          isLoading={isLoading}
        />
      )}
    </>
  )
}

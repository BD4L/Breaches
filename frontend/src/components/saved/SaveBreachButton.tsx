import React, { useState } from 'react'
import { Bookmark, BookmarkCheck, Heart, Star } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
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
  notes: string
  tags: string[]
  review_status: 'pending' | 'in_progress' | 'reviewed' | 'escalated' | 'closed'
  assigned_to: string
  due_date: string
}

export function SaveBreachButton({
  breach,
  isSaved = false,
  savedData,
  onSave,
  onRemove,
  className = ''
}: SaveBreachButtonProps) {
  const [isLoading, setIsLoading] = useState(false)

  const handleToggleSave = async () => {
    if (isSaved && onRemove) {
      setIsLoading(true)
      try {
        await onRemove(breach.id)
      } catch (error) {
        console.error('Failed to remove saved breach:', error)
      } finally {
        setIsLoading(false)
      }
    } else if (onSave) {
      setIsLoading(true)
      try {
        // Simple save with default values
        const defaultSaveData: SaveBreachData = {
          collection_name: 'Default',
          priority_level: 'medium',
          notes: '',
          tags: [],
          review_status: 'pending',
          assigned_to: '',
          due_date: ''
        }
        await onSave(breach.id, defaultSaveData)
      } catch (error) {
        console.error('Failed to save breach:', error)
      } finally {
        setIsLoading(false)
      }
    }
  }

  return (
    <Button
      variant={isSaved ? "default" : "ghost"}
      size="sm"
      onClick={handleToggleSave}
      disabled={isLoading}
      className={`
        ${className}
        transition-all duration-200 ease-in-out
        ${isSaved
          ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-md border-blue-600'
          : 'hover:bg-blue-50 text-blue-600 border-blue-200 hover:border-blue-300'
        }
        ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      {isSaved ? (
        <Star className="w-4 h-4 mr-1" fill="currentColor" />
      ) : (
        <Bookmark className="w-4 h-4 mr-1" />
      )}
      {isLoading ? 'Loading...' : (isSaved ? 'Saved' : 'Save')}
    </Button>
  )
}

import React, { useState, useEffect } from 'react'
import { Calendar, X } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

interface DateRangePickerProps {
  label: string
  value: { start?: string; end?: string }
  onChange: (range: { start?: string; end?: string }) => void
  placeholder?: string
}

export function DateRangePicker({ label, value, onChange, placeholder }: DateRangePickerProps) {
  const [startDate, setStartDate] = useState(value.start || '')
  const [endDate, setEndDate] = useState(value.end || '')

  useEffect(() => {
    setStartDate(value.start || '')
    setEndDate(value.end || '')
  }, [value])

  const handleStartDateChange = (date: string) => {
    setStartDate(date)
    onChange({ start: date || undefined, end: endDate || undefined })
  }

  const handleEndDateChange = (date: string) => {
    setEndDate(date)
    onChange({ start: startDate || undefined, end: date || undefined })
  }

  const handleClear = () => {
    setStartDate('')
    setEndDate('')
    onChange({ start: undefined, end: undefined })
  }

  const hasValue = startDate || endDate

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          <Calendar className="inline w-4 h-4 mr-1" />
          {label}
        </label>
        {hasValue && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="p-1 h-6 w-6 text-gray-400 hover:text-gray-600"
          >
            <X className="w-3 h-3" />
          </Button>
        )}
      </div>

      <div className="space-y-2">
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
            From
          </label>
          <Input
            type="date"
            value={startDate}
            onChange={(e) => handleStartDateChange(e.target.value)}
            className="w-full"
            placeholder="Start date"
          />
        </div>

        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
            To
          </label>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => handleEndDateChange(e.target.value)}
            className="w-full"
            placeholder="End date"
            min={startDate || undefined}
          />
        </div>
      </div>

      {hasValue && (
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {startDate && endDate ? (
            <>From {new Date(startDate).toLocaleDateString()} to {new Date(endDate).toLocaleDateString()}</>
          ) : startDate ? (
            <>From {new Date(startDate).toLocaleDateString()}</>
          ) : endDate ? (
            <>Until {new Date(endDate).toLocaleDateString()}</>
          ) : null}
        </div>
      )}
    </div>
  )
}

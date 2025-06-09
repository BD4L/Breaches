import React, { useState, useEffect, useRef } from 'react'
import { Search, X, Filter, Calendar, Users, Building, AlertCircle } from 'lucide-react'

interface SearchFilter {
  field: string
  operator: string
  value: string
  label: string
}

interface AdvancedSearchInputProps {
  value: string
  onChange: (value: string, filters: SearchFilter[]) => void
  placeholder?: string
  className?: string
}

const SEARCH_FIELDS = [
  { value: 'organization_name', label: 'Organization', icon: Building },
  { value: 'what_was_leaked', label: 'Data Compromised', icon: AlertCircle },
  { value: 'source_name', label: 'Source', icon: Filter },
  { value: 'affected_individuals', label: 'People Affected', icon: Users },
  { value: 'breach_date', label: 'Breach Date', icon: Calendar },
  { value: 'tags_keywords', label: 'Keywords', icon: Search },
]

const OPERATORS = [
  { value: 'contains', label: 'contains', fields: ['text'] },
  { value: 'equals', label: 'equals', fields: ['text', 'number'] },
  { value: 'greater_than', label: '>', fields: ['number', 'date'] },
  { value: 'less_than', label: '<', fields: ['number', 'date'] },
  { value: 'between', label: 'between', fields: ['number', 'date'] },
]

export function AdvancedSearchInput({ value, onChange, placeholder = 'Search breaches...', className = '' }: AdvancedSearchInputProps) {
  const [inputValue, setInputValue] = useState(value)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [filters, setFilters] = useState<SearchFilter[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const timeoutRef = useRef<NodeJS.Timeout>()
  const inputRef = useRef<HTMLInputElement>(null)

  // Common search suggestions
  const SUGGESTIONS = [
    'healthcare', 'ransomware', 'phishing', 'malware', 'data breach',
    'social security', 'credit card', 'personal information', 'medical records',
    'financial data', 'employee data', 'customer data', 'email addresses'
  ]

  useEffect(() => {
    setInputValue(value)
  }, [value])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setInputValue(newValue)

    // Show suggestions when typing
    if (newValue.length > 2) {
      const filtered = SUGGESTIONS.filter(s => 
        s.toLowerCase().includes(newValue.toLowerCase())
      )
      setSuggestions(filtered.slice(0, 5))
      setShowSuggestions(true)
    } else {
      setShowSuggestions(false)
    }

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    timeoutRef.current = setTimeout(() => {
      onChange(newValue, filters)
    }, 300)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      setShowSuggestions(false)
      onChange(inputValue, filters)
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  const addFilter = (filter: SearchFilter) => {
    const newFilters = [...filters, filter]
    setFilters(newFilters)
    onChange(inputValue, newFilters)
  }

  const removeFilter = (index: number) => {
    const newFilters = filters.filter((_, i) => i !== index)
    setFilters(newFilters)
    onChange(inputValue, newFilters)
  }

  const selectSuggestion = (suggestion: string) => {
    setInputValue(suggestion)
    setShowSuggestions(false)
    onChange(suggestion, filters)
    inputRef.current?.focus()
  }

  const clearAll = () => {
    setInputValue('')
    setFilters([])
    setShowSuggestions(false)
    onChange('', [])
    inputRef.current?.focus()
  }

  return (
    <div className={`relative ${className}`}>
      {/* Main Search Input */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <Search className="w-4 h-4 text-gray-400" />
        </div>
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => inputValue.length > 2 && setShowSuggestions(true)}
          placeholder={placeholder}
          className="w-full pl-10 pr-20 py-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors"
        />
        <div className="absolute inset-y-0 right-0 flex items-center pr-3 space-x-2">
          {(inputValue || filters.length > 0) && (
            <button
              onClick={clearAll}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              title="Clear all"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className={`p-1 transition-colors ${
              showAdvanced || filters.length > 0
                ? 'text-blue-500 hover:text-blue-600'
                : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
            }`}
            title="Advanced filters"
          >
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Search Suggestions */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg z-50">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => selectSuggestion(suggestion)}
              className="w-full px-4 py-2 text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 first:rounded-t-lg last:rounded-b-lg transition-colors"
            >
              <Search className="w-3 h-3 inline mr-2 text-gray-400" />
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* Active Filters */}
      {filters.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {filters.map((filter, index) => (
            <div
              key={index}
              className="inline-flex items-center px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded-full text-sm"
            >
              <span className="font-medium">{filter.label}:</span>
              <span className="ml-1">{filter.operator} "{filter.value}"</span>
              <button
                onClick={() => removeFilter(index)}
                className="ml-2 text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Advanced Search Panel */}
      {showAdvanced && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg z-40 p-4">
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Advanced Search</h3>
          
          {/* Quick Filters */}
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                Quick Filters
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => addFilter({
                    field: 'affected_individuals',
                    operator: 'greater_than',
                    value: '1000',
                    label: 'High Impact (>1K affected)'
                  })}
                  className="px-3 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-full text-xs hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
                >
                  High Impact Breaches
                </button>
                <button
                  onClick={() => addFilter({
                    field: 'breach_date',
                    operator: 'greater_than',
                    value: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                    label: 'Recent (Last 7 days)'
                  })}
                  className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
                >
                  Recent Breaches
                </button>
                <button
                  onClick={() => addFilter({
                    field: 'what_was_leaked',
                    operator: 'contains',
                    value: 'social security',
                    label: 'SSN Compromised'
                  })}
                  className="px-3 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 rounded-full text-xs hover:bg-yellow-200 dark:hover:bg-yellow-900/50 transition-colors"
                >
                  SSN Involved
                </button>
                <button
                  onClick={() => addFilter({
                    field: 'what_was_leaked',
                    operator: 'contains',
                    value: 'medical',
                    label: 'Medical Data'
                  })}
                  className="px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full text-xs hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors"
                >
                  Medical Records
                </button>
              </div>
            </div>

            {/* Search Tips */}
            <div className="border-t border-gray-200 dark:border-gray-600 pt-3">
              <label className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                Search Tips
              </label>
              <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                <p>• Use quotes for exact phrases: "data breach"</p>
                <p>• Use OR for multiple terms: healthcare OR medical</p>
                <p>• Use - to exclude terms: breach -test</p>
                <p>• Search specific fields with filters above</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
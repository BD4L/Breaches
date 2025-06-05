import React, { useState, useEffect, useRef } from 'react'
import { Search } from 'lucide-react'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export function SearchInput({ value, onChange, placeholder = 'Search...', className = '' }: SearchInputProps) {
  const [inputValue, setInputValue] = useState(value)
  const timeoutRef = useRef<NodeJS.Timeout>()

  // Update local state when prop changes
  useEffect(() => {
    setInputValue(value)
  }, [value])

  // Handle input with debouncing
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setInputValue(newValue)

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    timeoutRef.current = setTimeout(() => {
      onChange(newValue)
    }, 300)
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return (
    <div className="relative">
      <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
        <Search className="w-4 h-4 text-gray-400" />
      </div>
      <input
        type="text"
        value={inputValue}
        onChange={handleChange}
        placeholder={placeholder}
        className={`pl-10 pr-4 py-2 w-full rounded-lg bg-dark-700 border border-dark-600 text-white placeholder-gray-500 focus:ring-1 focus:ring-teal focus:border-teal outline-none transition-colors ${className}`}
      />
    </div>
  )
} 
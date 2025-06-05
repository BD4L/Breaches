import React, { useState, useEffect } from 'react'
import { Users, X } from 'lucide-react'
import { Button } from '../ui/Button'

interface NumericSliderProps {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  formatValue?: (value: number) => string
}

export function NumericSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 100000,
  step = 100,
  formatValue = (val) => val.toLocaleString()
}: NumericSliderProps) {
  const [sliderValue, setSliderValue] = useState(value)

  useEffect(() => {
    setSliderValue(value)
  }, [value])

  const handleSliderChange = (newValue: number) => {
    setSliderValue(newValue)
    onChange(newValue)
  }

  const handleClear = () => {
    setSliderValue(0)
    onChange(0)
  }

  const hasValue = sliderValue > 0

  // Predefined quick values
  const quickValues = [
    { label: 'Any', value: 0 },
    { label: '100+', value: 100 },
    { label: '500+', value: 500 },
    { label: '1K+', value: 1000 },
    { label: '5K+', value: 5000 },
    { label: '10K+', value: 10000 },
    { label: '50K+', value: 50000 },
    { label: '100K+', value: 100000 },
  ]

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          <Users className="inline w-4 h-4 mr-1" />
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

      {/* Quick Value Buttons */}
      <div className="flex flex-wrap gap-1">
        {quickValues.map((quick) => (
          <button
            key={quick.value}
            onClick={() => handleSliderChange(quick.value)}
            className={`px-2 py-1 text-xs rounded-md transition-colors ${
              sliderValue === quick.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
            }`}
          >
            {quick.label}
          </button>
        ))}
      </div>

      {/* Custom Slider */}
      <div className="space-y-2">
        <div className="relative">
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={sliderValue}
            onChange={(e) => handleSliderChange(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg cursor-pointer dark:bg-gray-700"
            style={{
              WebkitAppearance: 'none',
              appearance: 'none',
              background: 'transparent',
              outline: 'none'
            }}
          />
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
            <span>{formatValue(min)}</span>
            <span>{formatValue(max)}</span>
          </div>
        </div>

        {hasValue && (
          <div className="text-center">
            <span className="inline-block px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full text-sm font-medium">
              Minimum: {formatValue(sliderValue)} people
            </span>
          </div>
        )}
      </div>

      <style dangerouslySetInnerHTML={{
        __html: `
          input[type="range"]::-webkit-slider-track {
            height: 8px;
            border-radius: 4px;
            background: #e5e7eb;
            border: none;
          }

          input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            height: 20px;
            width: 20px;
            border-radius: 50%;
            background: #2563eb;
            cursor: grab;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
            margin-top: -6px;
          }

          input[type="range"]::-webkit-slider-thumb:hover {
            background: #1d4ed8;
            transform: scale(1.1);
          }

          input[type="range"]::-webkit-slider-thumb:active {
            cursor: grabbing;
          }

          input[type="range"]::-moz-range-track {
            height: 8px;
            border-radius: 4px;
            background: #e5e7eb;
            border: none;
          }

          input[type="range"]::-moz-range-thumb {
            height: 20px;
            width: 20px;
            border-radius: 50%;
            background: #2563eb;
            cursor: grab;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
          }

          input[type="range"]::-moz-range-thumb:hover {
            background: #1d4ed8;
          }
        `
      }} />
    </div>
  )
}

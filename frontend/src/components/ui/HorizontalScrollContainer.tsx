import React, { useRef, useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface HorizontalScrollContainerProps {
  children: React.ReactNode
  className?: string
  showScrollButtons?: boolean
  showScrollIndicator?: boolean
}

export function HorizontalScrollContainer({ 
  children, 
  className = '', 
  showScrollButtons = true,
  showScrollIndicator = true 
}: HorizontalScrollContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)
  const [isScrolling, setIsScrolling] = useState(false)

  const checkScrollability = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current
      setCanScrollLeft(scrollLeft > 0)
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1)
    }
  }

  useEffect(() => {
    checkScrollability()
    const handleResize = () => checkScrollability()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const scrollLeft = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: -300, behavior: 'smooth' })
    }
  }

  const scrollRight = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: 300, behavior: 'smooth' })
    }
  }

  const handleScroll = () => {
    checkScrollability()
    setIsScrolling(true)
    
    // Hide scroll indicator after scrolling stops
    const timer = setTimeout(() => {
      setIsScrolling(false)
    }, 1000)
    
    return () => clearTimeout(timer)
  }

  return (
    <div className="relative group">
      {/* Left scroll button */}
      {showScrollButtons && canScrollLeft && (
        <button
          onClick={scrollLeft}
          className="absolute left-2 top-1/2 -translate-y-1/2 z-10 bg-white dark:bg-gray-800 shadow-lg rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-gray-50 dark:hover:bg-gray-700"
          aria-label="Scroll left"
        >
          <ChevronLeft className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        </button>
      )}

      {/* Right scroll button */}
      {showScrollButtons && canScrollRight && (
        <button
          onClick={scrollRight}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-10 bg-white dark:bg-gray-800 shadow-lg rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-gray-50 dark:hover:bg-gray-700"
          aria-label="Scroll right"
        >
          <ChevronRight className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        </button>
      )}

      {/* Scroll container */}
      <div
        ref={scrollRef}
        className={`overflow-x-auto scrollbar-thin ${className}`}
        onScroll={handleScroll}
        style={{
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgb(156 163 175) rgb(243 244 246)'
        }}
      >
        {children}
      </div>

      {/* Scroll indicator */}
      {showScrollIndicator && (canScrollLeft || canScrollRight) && (
        <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-blue-500/30 to-transparent transition-opacity duration-300 ${
          isScrolling ? 'opacity-100' : 'opacity-0 group-hover:opacity-60'
        }`}>
          {/* Progress indicator */}
          <div 
            className="h-full bg-blue-500 transition-all duration-150"
            style={{
              width: scrollRef.current 
                ? `${(scrollRef.current.scrollLeft / (scrollRef.current.scrollWidth - scrollRef.current.clientWidth)) * 100}%`
                : '0%'
            }}
          />
        </div>
      )}

      {/* Gradient overlays to indicate more content */}
      {canScrollLeft && (
        <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-white dark:from-gray-800 to-transparent pointer-events-none z-5" />
      )}
      {canScrollRight && (
        <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-white dark:from-gray-800 to-transparent pointer-events-none z-5" />
      )}
    </div>
  )
}

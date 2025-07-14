import React, { useEffect, useRef, useState, useCallback } from 'react'

interface HorizontalScrollbarProps {
  targetRef: React.RefObject<HTMLElement>
  className?: string
}

export function HorizontalScrollbar({ targetRef, className = '' }: HorizontalScrollbarProps) {
  const scrollbarRef = useRef<HTMLDivElement>(null)
  const thumbRef = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)
  const [thumbWidth, setThumbWidth] = useState(0)
  const [thumbPosition, setThumbPosition] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragStartScrollLeft, setDragStartScrollLeft] = useState(0)

  const updateScrollbar = useCallback(() => {
    if (!targetRef.current || !scrollbarRef.current) return

    const target = targetRef.current
    const scrollbar = scrollbarRef.current
    
    const scrollWidth = target.scrollWidth
    const clientWidth = target.clientWidth
    const scrollLeft = target.scrollLeft
    
    // Show scrollbar only if content overflows
    const shouldShow = scrollWidth > clientWidth
    setIsVisible(shouldShow)
    
    if (!shouldShow) return

    // Calculate thumb width and position
    const scrollbarWidth = scrollbar.clientWidth
    const newThumbWidth = Math.max((clientWidth / scrollWidth) * scrollbarWidth, 20) // Minimum thumb width of 20px
    const maxThumbPosition = scrollbarWidth - newThumbWidth
    const newThumbPosition = (scrollLeft / (scrollWidth - clientWidth)) * maxThumbPosition
    
    setThumbWidth(newThumbWidth)
    setThumbPosition(Math.max(0, Math.min(newThumbPosition, maxThumbPosition)))
  }, [targetRef])

  // Update scrollbar when target scrolls
  useEffect(() => {
    const target = targetRef.current
    if (!target) return

    const handleScroll = () => {
      if (!isDragging) {
        updateScrollbar()
      }
    }

    target.addEventListener('scroll', handleScroll, { passive: true })
    return () => target.removeEventListener('scroll', handleScroll)
  }, [targetRef, updateScrollbar, isDragging])

  // Update scrollbar on resize
  useEffect(() => {
    const handleResize = () => updateScrollbar()
    
    window.addEventListener('resize', handleResize)
    updateScrollbar() // Initial update
    
    return () => window.removeEventListener('resize', handleResize)
  }, [updateScrollbar])

  // Handle mouse down on thumb
  const handleThumbMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    setDragStartX(e.clientX)
    setDragStartScrollLeft(targetRef.current?.scrollLeft || 0)
  }

  // Handle mouse down on track (jump to position)
  const handleTrackMouseDown = (e: React.MouseEvent) => {
    if (!targetRef.current || !scrollbarRef.current || e.target === thumbRef.current) return
    
    const scrollbar = scrollbarRef.current
    const target = targetRef.current
    const rect = scrollbar.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const scrollbarWidth = scrollbar.clientWidth
    const scrollRatio = clickX / scrollbarWidth
    const maxScrollLeft = target.scrollWidth - target.clientWidth
    
    target.scrollLeft = scrollRatio * maxScrollLeft
  }

  // Handle mouse move during drag
  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!targetRef.current || !scrollbarRef.current) return

      const target = targetRef.current
      const scrollbar = scrollbarRef.current
      const deltaX = e.clientX - dragStartX
      const scrollbarWidth = scrollbar.clientWidth
      const maxScrollLeft = target.scrollWidth - target.clientWidth
      const scrollRatio = deltaX / (scrollbarWidth - thumbWidth)
      
      target.scrollLeft = dragStartScrollLeft + (scrollRatio * maxScrollLeft)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, dragStartX, dragStartScrollLeft, thumbWidth, targetRef])

  if (!isVisible) return null

  return (
    <div className={`relative h-3 bg-gray-100 dark:bg-gray-700 rounded-full cursor-pointer ${className}`}>
      <div
        ref={scrollbarRef}
        className="absolute inset-0 rounded-full"
        onMouseDown={handleTrackMouseDown}
      >
        <div
          ref={thumbRef}
          className="absolute top-0 h-full bg-gray-400 dark:bg-gray-500 rounded-full cursor-grab active:cursor-grabbing hover:bg-gray-500 dark:hover:bg-gray-400 transition-colors"
          style={{
            width: `${thumbWidth}px`,
            left: `${thumbPosition}px`,
          }}
          onMouseDown={handleThumbMouseDown}
        />
      </div>
    </div>
  )
}

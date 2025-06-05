import React from 'react'
import { cn } from '../../lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'success'
  children: React.ReactNode
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = 'default', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
          {
            'border-transparent bg-teal-600 text-white hover:bg-teal-700 dark:bg-teal-500/90 dark:hover:bg-teal-500': variant === 'default',
            'border-transparent bg-gray-100 text-gray-900 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600': variant === 'secondary',
            'border-transparent bg-red-600 text-white hover:bg-red-700 dark:bg-red-500/90 dark:hover:bg-red-500': variant === 'destructive',
            'border-transparent bg-green-600 text-white hover:bg-green-700 dark:bg-green-500/90 dark:hover:bg-green-500': variant === 'success',
            'text-gray-900 border-gray-300 dark:text-gray-100 dark:border-gray-600': variant === 'outline',
          },
          className
        )}
        {...props}
      />
    )
  }
)

Badge.displayName = 'Badge'

export { Badge }

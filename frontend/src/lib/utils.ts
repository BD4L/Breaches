import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, parseISO, isValid } from "date-fns"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateString: string | null): string {
  if (!dateString) return 'Unknown'
  
  try {
    const date = parseISO(dateString)
    if (!isValid(date)) return dateString
    return format(date, 'MMM dd, yyyy')
  } catch {
    return dateString
  }
}

export function formatNumber(num: number | null): string {
  if (num === null || num === undefined) return 'Unknown'
  return new Intl.NumberFormat().format(num)
}

export function formatAffectedCount(count: number | null): string {
  if (count === null || count === undefined) return 'Unknown'
  
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`
  } else if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`
  }
  return count.toString()
}

export function getSourceTypeColor(sourceType: string): string {
  const colors: Record<string, string> = {
    'State AG': 'bg-blue-100 text-blue-800',
    'Government Portal': 'bg-green-100 text-green-800',
    'News Feed': 'bg-orange-100 text-orange-800',
    'Breach Database': 'bg-purple-100 text-purple-800',
    'Company IR': 'bg-gray-100 text-gray-800',
    'API': 'bg-indigo-100 text-indigo-800',
    'State Cybersecurity': 'bg-red-100 text-red-800',
    'State Agency': 'bg-teal-100 text-teal-800'
  }
  
  return colors[sourceType] || 'bg-gray-100 text-gray-800'
}

export function getSeverityColor(affectedCount: number | null): string {
  if (!affectedCount) return 'text-gray-500'
  
  if (affectedCount >= 100000) return 'text-red-600 font-semibold'
  if (affectedCount >= 10000) return 'text-orange-600 font-medium'
  if (affectedCount >= 1000) return 'text-yellow-600'
  return 'text-gray-600'
}

export function truncateText(text: string | null, maxLength: number = 100): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

export function extractDomain(url: string | null): string {
  if (!url) return ''
  
  try {
    const domain = new URL(url).hostname
    return domain.replace('www.', '')
  } catch {
    return url
  }
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

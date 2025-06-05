import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ExpandedState,
} from '@tanstack/react-table'
import { getBreaches, type BreachRecord } from '../../lib/supabase'
import { formatDate, formatAffectedCount, getSourceTypeColor, getSeverityColor, truncateText } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { BreachDetail } from '../breach/BreachDetail'

interface BreachTableProps {
  filters: {
    search: string
    sourceTypes: string[]
    selectedSources: number[]
    minAffected: number
    scrapedDateRange: string
    breachDateRange: string
    publicationDateRange: string
  }
}

export function BreachTable({ filters }: BreachTableProps) {
  const [data, setData] = useState<BreachRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'publication_date', desc: true }
  ])
  const [expanded, setExpanded] = useState<ExpandedState>({})
  const [totalCount, setTotalCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 50

  // Add debouncing to prevent excessive API calls
  const [debouncedFilters, setDebouncedFilters] = useState(filters)
  const debounceTimeoutRef = useRef<NodeJS.Timeout>()

  const columns = useMemo<ColumnDef<BreachRecord>[]>(
    () => [
      {
        id: 'expander',
        header: '',
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="sm"
            onClick={row.getToggleExpandedHandler()}
            className="p-1 text-gray-500 dark:text-gray-400 hover:text-teal-600 dark:hover:text-teal-400"
          >
            {row.getIsExpanded() ? '▼' : '▶'}
          </Button>
        ),
        size: 40,
      },
      {
        accessorKey: 'organization_name',
        header: 'Organization',
        cell: ({ getValue, row }) => (
          <div className="min-w-0">
            <div className="font-medium text-gray-900 dark:text-white truncate">
              {getValue() as string}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
              {row.original.source_name}
            </div>
          </div>
        ),
        size: 250,
      },
      {
        accessorKey: 'source_type',
        header: 'Source Type',
        cell: ({ getValue }) => (
          <Badge className={getSourceTypeColor(getValue() as string)}>
            {getValue() as string}
          </Badge>
        ),
        size: 120,
      },
      {
        accessorKey: 'affected_individuals',
        header: 'Affected',
        cell: ({ getValue }) => {
          const count = getValue() as number | null
          return (
            <span className={getSeverityColor(count)}>
              {formatAffectedCount(count)}
            </span>
          )
        },
        size: 100,
      },
      {
        accessorKey: 'breach_date',
        header: 'Breach Date',
        cell: ({ getValue }) => (
          <span className="text-sm text-gray-700 dark:text-gray-300">
            {formatDate(getValue() as string)}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: 'publication_date',
        header: 'Published',
        cell: ({ getValue }) => (
          <span className="text-sm text-gray-700 dark:text-gray-300">
            {formatDate(getValue() as string)}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: 'what_was_leaked',
        header: 'Data Compromised',
        cell: ({ getValue }) => (
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {truncateText(getValue() as string, 80)}
          </span>
        ),
        size: 200,
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex space-x-2">
            {row.original.notice_document_url && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(row.original.notice_document_url!, '_blank')}
                className="border-gray-200 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/20"
              >
                📄 Notice
              </Button>
            )}
            {row.original.item_url && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(row.original.item_url!, '_blank')}
                className="border-gray-200 dark:border-gray-600 hover:bg-purple-50 dark:hover:bg-purple-900/20"
              >
                🔗 Source
              </Button>
            )}
          </div>
        ),
        size: 150,
      },
    ],
    []
  )

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      expanded,
    },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getRowCanExpand: () => true,
  })

  // Debounce filter changes to prevent excessive API calls
  useEffect(() => {
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current)
    }

    debounceTimeoutRef.current = setTimeout(() => {
      setDebouncedFilters(filters)
    }, 300)

    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current)
      }
    }
  }, [filters])

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      setError(null)

      console.log('🔍 Loading breach data with parameters:', {
        currentPage,
        pageSize,
        filters: debouncedFilters,
        sorting
      })

      try {
        const sortBy = sorting[0]?.id || 'publication_date'
        const sortOrder = sorting[0]?.desc ? 'desc' : 'asc'

        const queryParams = {
          page: currentPage,
          limit: pageSize,
          sourceTypes: debouncedFilters.sourceTypes,
          selectedSources: debouncedFilters.selectedSources,
          minAffected: debouncedFilters.minAffected,
          search: debouncedFilters.search,
          sortBy,
          sortOrder,
          scrapedDateRange: debouncedFilters.scrapedDateRange,
          breachDateRange: debouncedFilters.breachDateRange,
          publicationDateRange: debouncedFilters.publicationDateRange,
        }

        console.log('📊 Query parameters:', queryParams)

        const result = await getBreaches(queryParams)
        console.log('📥 Supabase query result:', result)

        const { data: breaches, error, count } = result

        if (error) {
          console.error('❌ Supabase error:', error)
          throw error
        }

        console.log('✅ Successfully loaded breaches:', {
          breachCount: breaches?.length || 0,
          totalCount: count,
          firstBreach: breaches?.[0]?.organization_name || 'None'
        })

        setData(breaches || [])
        setTotalCount(count || 0)
      } catch (err) {
        console.error('💥 Error loading breach data:', err)
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [debouncedFilters, sorting, currentPage])

  const totalPages = Math.ceil(totalCount / pageSize)

  if (loading) {
    return (
      <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl rounded-2xl shadow-xl border border-gray-200/50 dark:border-gray-700/50 overflow-hidden">
        {/* Loading Header */}
        <div className="px-8 py-6 bg-gradient-to-r from-gray-50 to-blue-50 dark:from-gray-800/80 dark:to-gray-700/80 border-b border-gray-200/50 dark:border-gray-700/50">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-teal-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                <span className="text-white text-lg">🛡️</span>
              </div>
              <div>
                <div className="h-6 w-40 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse"></div>
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mt-2 animate-pulse"></div>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="px-4 py-2 bg-white/50 dark:bg-gray-800/50 rounded-xl border border-gray-200/50 dark:border-gray-700/50 shadow-sm">
                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                <div className="h-6 w-16 bg-gray-200 dark:bg-gray-700 rounded mt-1 animate-pulse"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Loading Table */}
        <div className="p-8">
          <div className="space-y-4">
            {/* Header Row */}
            <div className="flex space-x-4 pb-4 border-b border-gray-200/50 dark:border-gray-700/50">
              {[...Array(7)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse flex-1"></div>
              ))}
            </div>

            {/* Data Rows */}
            {[...Array(8)].map((_, i) => (
              <div key={i} className="flex space-x-4 py-3">
                {[...Array(7)].map((_, j) => (
                  <div key={j} className={`h-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse flex-1 ${j === 0 ? 'w-8' : ''}`}></div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-red-200 dark:border-red-700 p-6">
        <div className="text-red-600 dark:text-red-400">
          <h3 className="font-medium">Error loading breach data</h3>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl rounded-2xl shadow-xl border border-gray-200/50 dark:border-gray-700/50 overflow-hidden">
      {/* Modern Header */}
      <div className="px-8 py-6 bg-gradient-to-r from-gray-50 to-blue-50 dark:from-gray-800/80 dark:to-gray-700/80 border-b border-gray-200/50 dark:border-gray-700/50">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-teal-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
              <span className="text-white text-lg">🛡️</span>
            </div>
            <div>
              <h2 className="text-xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-teal-300 bg-clip-text text-transparent">
                Security Incidents
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Real-time breach monitoring
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="px-4 py-2 bg-white/50 dark:bg-gray-800/50 rounded-xl border border-gray-200/50 dark:border-gray-700/50 shadow-sm">
              <div className="text-sm font-medium text-gray-600 dark:text-gray-300">Total Records</div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {totalCount.toLocaleString()}
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-teal-400 rounded-full animate-pulse"></div>
              <span className="text-sm text-gray-500 dark:text-gray-400">Live</span>
            </div>
          </div>
        </div>
      </div>

      {/* Modern Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700/80 dark:to-gray-600/80">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-6 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider border-b border-gray-200/50 dark:border-gray-600/50"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={
                          header.column.getCanSort()
                            ? 'cursor-pointer select-none flex items-center space-x-2 hover:text-teal-600 dark:hover:text-teal-400 transition-colors duration-200'
                            : 'flex items-center space-x-2'
                        }
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <div className="flex flex-col">
                          {{
                            asc: <span className="text-teal-500">▲</span>,
                            desc: <span className="text-teal-500">▼</span>,
                          }[header.column.getIsSorted() as string] ?? (
                            header.column.getCanSort() && (
                              <span className="text-gray-300 dark:text-gray-600">⇅</span>
                            )
                          )}
                        </div>
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white/50 dark:bg-gray-800/50 divide-y divide-gray-200/30 dark:divide-gray-700/30">
            {table.getRowModel().rows.map((row, index) => (
              <React.Fragment key={row.id}>
                <tr className={`
                  group transition-all duration-200 hover:bg-gradient-to-r hover:from-teal-50/50 hover:to-purple-50/50
                  dark:hover:from-teal-900/10 dark:hover:to-purple-900/10 hover:shadow-sm
                  ${index % 2 === 0 ? 'bg-white/30 dark:bg-gray-800/30' : 'bg-gray-50/30 dark:bg-gray-700/30'}
                `}>
                  {row.getVisibleCells().map(cell => (
                    <td
                      key={cell.id}
                      className="px-6 py-5 transition-all duration-200 group-hover:px-7"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {row.getIsExpanded() && (
                  <tr>
                    <td colSpan={columns.length} className="px-6 py-4 bg-gray-50/70 dark:bg-gray-700/70 backdrop-blur-sm">
                      <BreachDetail breach={row.original} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modern Pagination */}
      {totalPages > 1 && (
        <div className="px-8 py-6 bg-gradient-to-r from-gray-50 to-blue-50 dark:from-gray-800/80 dark:to-gray-700/80 border-t border-gray-200/50 dark:border-gray-700/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-600 dark:text-gray-300 font-medium">
                Showing <span className="font-bold text-teal-600 dark:text-teal-400">{currentPage * pageSize + 1}</span> to{' '}
                <span className="font-bold text-teal-600 dark:text-teal-400">{Math.min((currentPage + 1) * pageSize, totalCount)}</span> of{' '}
                <span className="font-bold text-teal-600 dark:text-teal-400">{totalCount}</span> results
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(0, prev - 1))}
                disabled={currentPage === 0}
                className="px-4 py-2 rounded-xl border-gray-300 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/20 hover:border-teal-300 dark:hover:border-teal-600 transition-all duration-200"
              >
                ← Previous
              </Button>
              <div className="flex items-center px-4 py-2 bg-white/50 dark:bg-gray-800/50 rounded-xl border border-gray-200/50 dark:border-gray-700/50 shadow-sm">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                  Page <span className="font-bold text-teal-600 dark:text-teal-400">{currentPage + 1}</span> of{' '}
                  <span className="font-bold text-teal-600 dark:text-teal-400">{totalPages}</span>
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages - 1, prev + 1))}
                disabled={currentPage >= totalPages - 1}
                className="px-4 py-2 rounded-xl border-gray-300 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/20 hover:border-teal-300 dark:hover:border-teal-600 transition-all duration-200"
              >
                Next →
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

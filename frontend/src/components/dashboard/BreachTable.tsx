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
            className="p-1"
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
          <span className="text-sm">
            {formatDate(getValue() as string)}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: 'publication_date',
        header: 'Published',
        cell: ({ getValue }) => (
          <span className="text-sm">
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
              >
                📄 Notice
              </Button>
            )}
            {row.original.item_url && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(row.original.item_url!, '_blank')}
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
      <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 overflow-hidden">
        {/* Loading Header */}
        <div className="px-6 py-4 border-b border-slate-700/50">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-4">
              <div className="h-5 w-40 bg-slate-700 rounded animate-pulse"></div>
              <div className="flex space-x-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-6 w-16 bg-slate-700 rounded animate-pulse"></div>
                ))}
              </div>
            </div>
            <div className="h-6 w-20 bg-slate-700 rounded animate-pulse"></div>
          </div>
        </div>

        {/* Loading Table */}
        <div className="p-6">
          <div className="space-y-3">
            {/* Header Row */}
            <div className="flex space-x-4 pb-3 border-b border-slate-700/50">
              {[...Array(7)].map((_, i) => (
                <div key={i} className="h-4 bg-slate-700 rounded animate-pulse flex-1"></div>
              ))}
            </div>

            {/* Data Rows */}
            {[...Array(10)].map((_, i) => (
              <div key={i} className="flex space-x-4 py-2">
                {[...Array(7)].map((_, j) => (
                  <div key={j} className="h-4 bg-slate-700/50 rounded animate-pulse flex-1"></div>
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
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 overflow-hidden">
      {/* Dark Theme Header */}
      <div className="px-6 py-4 border-b border-slate-700/50">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <span className="text-white font-medium">🛡️ Breach Notifications</span>
              <div className="flex items-center space-x-2 ml-4">
                <button className="px-3 py-1 text-xs bg-slate-700 text-slate-300 rounded hover:bg-slate-600 transition-colors">
                  🔍 Breach Notifications
                </button>
                <button className="px-3 py-1 text-xs text-slate-400 hover:text-white transition-colors">
                  📰 Cybersecurity News
                </button>
                <button className="px-3 py-1 text-xs text-slate-400 hover:text-white transition-colors">
                  🔧 Scraper Control
                </button>
                <button className="px-3 py-1 text-xs text-slate-400 hover:text-white transition-colors">
                  📊 Source Summary
                </button>
                <button className="px-3 py-1 text-xs text-slate-400 hover:text-white transition-colors">
                  ⚠️ Issues
                </button>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <button className="px-3 py-1 text-xs text-slate-400 hover:text-white transition-colors">
              Clear All
            </button>
          </div>
        </div>
      </div>

      {/* Dark Theme Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-900/50">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider border-b border-slate-700/50"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={
                          header.column.getCanSort()
                            ? 'cursor-pointer select-none flex items-center space-x-1 hover:text-white transition-colors duration-200'
                            : 'flex items-center space-x-1'
                        }
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <div className="flex flex-col">
                          {{
                            asc: <span className="text-blue-400">▲</span>,
                            desc: <span className="text-blue-400">▼</span>,
                          }[header.column.getIsSorted() as string] ?? (
                            header.column.getCanSort() && (
                              <span className="text-slate-600">⇅</span>
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
          <tbody className="bg-slate-800/30 divide-y divide-slate-700/30">
            {table.getRowModel().rows.map((row, index) => (
              <React.Fragment key={row.id}>
                <tr className={`
                  group transition-all duration-200 hover:bg-slate-700/30
                  ${index % 2 === 0 ? 'bg-slate-800/20' : 'bg-slate-900/20'}
                `}>
                  {row.getVisibleCells().map(cell => (
                    <td
                      key={cell.id}
                      className="px-4 py-3 text-sm text-slate-300"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {row.getIsExpanded() && (
                  <tr>
                    <td colSpan={columns.length} className="px-6 py-4 bg-gray-50 dark:bg-gray-700">
                      <BreachDetail breach={row.original} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Dark Theme Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-4 bg-slate-900/50 border-t border-slate-700/50">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-400">
              Showing <span className="text-white font-medium">{currentPage * pageSize + 1}</span> to{' '}
              <span className="text-white font-medium">{Math.min((currentPage + 1) * pageSize, totalCount)}</span> of{' '}
              <span className="text-white font-medium">{totalCount}</span> results
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(0, prev - 1))}
                disabled={currentPage === 0}
                className="px-3 py-1 text-xs bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ← Previous
              </Button>
              <div className="px-3 py-1 text-xs text-slate-400">
                Page <span className="text-white font-medium">{currentPage + 1}</span> of{' '}
                <span className="text-white font-medium">{totalPages}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages - 1, prev + 1))}
                disabled={currentPage >= totalPages - 1}
                className="px-3 py-1 text-xs bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
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

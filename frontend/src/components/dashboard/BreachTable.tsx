import React, { useState, useEffect, useMemo } from 'react'
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

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      setError(null)
      
      try {
        const sortBy = sorting[0]?.id || 'publication_date'
        const sortOrder = sorting[0]?.desc ? 'desc' : 'asc'
        
        const { data: breaches, error, count } = await getBreaches({
          page: currentPage,
          limit: pageSize,
          sourceTypes: filters.sourceTypes,
          selectedSources: filters.selectedSources,
          minAffected: filters.minAffected,
          search: filters.search,
          sortBy,
          sortOrder,
          scrapedDateRange: filters.scrapedDateRange,
          breachDateRange: filters.breachDateRange,
          publicationDateRange: filters.publicationDateRange,
        })

        if (error) throw error

        setData(breaches || [])
        setTotalCount(count || 0)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [filters, sorting, currentPage])

  const totalPages = Math.ceil(totalCount / pageSize)

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="p-6">
          <div className="animate-pulse space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
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
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Breach Records
          </h2>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {totalCount.toLocaleString()} total records
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={
                          header.column.getCanSort()
                            ? 'cursor-pointer select-none flex items-center space-x-1'
                            : ''
                        }
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{
                          asc: ' 🔼',
                          desc: ' 🔽',
                        }[header.column.getIsSorted() as string] ?? null}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {table.getRowModel().rows.map(row => (
              <React.Fragment key={row.id}>
                <tr className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  {row.getVisibleCells().map(cell => (
                    <td
                      key={cell.id}
                      className="px-6 py-4 whitespace-nowrap"
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              Showing {currentPage * pageSize + 1} to {Math.min((currentPage + 1) * pageSize, totalCount)} of {totalCount} results
            </div>
            <div className="flex space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(0, prev - 1))}
                disabled={currentPage === 0}
              >
                Previous
              </Button>
              <span className="flex items-center px-3 py-1 text-sm">
                Page {currentPage + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages - 1, prev + 1))}
                disabled={currentPage >= totalPages - 1}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

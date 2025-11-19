/**
 * Dataset detail page with data table, aggregation controls, and charts.
 */

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/router';
import dynamic from 'next/dynamic';
import { useAuth } from '@/contexts/AuthContext';
import { getDataset, aggregateDataset } from '@/lib/api';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  SortingState,
  ColumnFiltersState,
} from '@tanstack/react-table';
import styles from '@/styles/DatasetView.module.css';

// Dynamic import for Highcharts to avoid SSR issues
const HighchartsReact = dynamic(() => import('highcharts-react-official'), {
  ssr: false,
});

// Import Highcharts on client side only
let Highcharts: any;
if (typeof window !== 'undefined') {
  Highcharts = require('highcharts');
}

interface ColumnInfo {
  name: string;
  type: 'categorical' | 'continuous';
}

interface Dataset {
  id: string;
  name: string;
  columns: ColumnInfo[];
  row_count: number;
  created_at: string;
  data: Record<string, any>[];
}

interface AggregationResult {
  group_value: string;
  aggregations: Record<string, { min: number; max: number; avg: number }>;
}

export default function DatasetView() {
  const router = useRouter();
  const { id } = router.query;
  const { isLoading: authLoading, isAuthenticated } = useAuth();

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Table state
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');

  // Aggregation state
  const [groupBy, setGroupBy] = useState<string>('');
  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [aggregationResults, setAggregationResults] = useState<AggregationResult[]>([]);
  const [isAggregating, setIsAggregating] = useState(false);
  const [showAggregation, setShowAggregation] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Fetch dataset
  useEffect(() => {
    if (id && isAuthenticated) {
      fetchDataset();
    }
  }, [id, isAuthenticated]);

  const fetchDataset = async () => {
    try {
      const response = await getDataset(id as string);
      setDataset(response.data);

      // Set default selections for aggregation
      const cats = response.data.columns.filter((c: ColumnInfo) => c.type === 'categorical');
      const conts = response.data.columns.filter((c: ColumnInfo) => c.type === 'continuous');
      if (cats.length > 0) setGroupBy(cats[0].name);
      if (conts.length > 0) setSelectedMetric(conts[0].name);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load dataset');
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch aggregation results
  const fetchAggregation = async () => {
    if (!groupBy || !selectedMetric || !id) return;

    setIsAggregating(true);
    try {
      const response = await aggregateDataset(id as string, {
        group_by: groupBy,
        metrics: [selectedMetric],
      });
      setAggregationResults(response.data.results);
      setShowAggregation(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Aggregation failed');
    } finally {
      setIsAggregating(false);
    }
  };

  // Get column categories
  const categoricalColumns = useMemo(() =>
    dataset?.columns.filter(c => c.type === 'categorical') || [],
    [dataset]
  );

  const continuousColumns = useMemo(() =>
    dataset?.columns.filter(c => c.type === 'continuous') || [],
    [dataset]
  );

  // Table columns configuration
  const columns = useMemo(() => {
    if (!dataset) return [];
    return dataset.columns.map(col => ({
      accessorKey: col.name,
      header: col.name,
      cell: (info: any) => {
        const value = info.getValue();
        if (value === null || value === undefined) return '-';
        if (col.type === 'continuous' && typeof value === 'number') {
          return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
        }
        return String(value);
      },
    }));
  }, [dataset]);

  // React Table instance
  const table = useReactTable({
    data: dataset?.data || [],
    columns,
    state: {
      sorting,
      columnFilters,
      globalFilter,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 20 },
    },
  });

  // Chart configuration
  const chartOptions = useMemo(() => {
    if (!aggregationResults.length || !selectedMetric) return null;

    const categories = aggregationResults.map(r => r.group_value);
    const avgData = aggregationResults.map(r => r.aggregations[selectedMetric]?.avg || 0);
    const minData = aggregationResults.map(r => r.aggregations[selectedMetric]?.min || 0);
    const maxData = aggregationResults.map(r => r.aggregations[selectedMetric]?.max || 0);

    // Use line chart for year (temporal), column chart otherwise
    // Note: 'column' = vertical bars (categorical on x-axis), 'bar' = horizontal bars
    const isYearGrouping = groupBy.toLowerCase().includes('year');
    const chartType = isYearGrouping ? 'line' : 'column';

    return {
      chart: { type: chartType },
      title: { text: `${selectedMetric} by ${groupBy}` },
      xAxis: {
        categories,
        title: { text: groupBy },
        labels: {
          rotation: isYearGrouping ? 0 : -45,
          style: { fontSize: '10px' },
        },
      },
      yAxis: {
        title: { text: selectedMetric },
      },
      series: [
        { name: 'Average', data: avgData, color: '#0070f3' },
        { name: 'Min', data: minData, color: '#00a86b' },
        { name: 'Max', data: maxData, color: '#ff6b6b' },
      ],
      tooltip: {
        shared: true,
        valueDecimals: 2,
      },
      legend: { enabled: true },
      credits: { enabled: false },
    };
  }, [aggregationResults, selectedMetric, groupBy]);

  // Loading states
  if (authLoading || isLoading) {
    return <div className={styles.loading}>Loading...</div>;
  }

  if (!isAuthenticated) {
    return null;
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>{error}</div>
        <button onClick={() => router.push('/dashboard')} className={styles.backButton}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  if (!dataset) {
    return <div className={styles.loading}>Dataset not found</div>;
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <button onClick={() => router.push('/dashboard')} className={styles.backButton}>
          ← Back
        </button>
        <h1>{dataset.name}</h1>
        <span className={styles.meta}>
          {dataset.row_count.toLocaleString()} rows • {dataset.columns.length} columns
        </span>
      </header>

      <main className={styles.main}>
        {/* Aggregation Controls */}
        <section className={styles.aggregationSection}>
          <h2>Data Aggregation</h2>
          <div className={styles.aggregationControls}>
            <div className={styles.controlGroup}>
              <label>Group by:</label>
              <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
                {categoricalColumns.map(col => (
                  <option key={col.name} value={col.name}>{col.name}</option>
                ))}
              </select>
            </div>
            <div className={styles.controlGroup}>
              <label>Metric:</label>
              <select value={selectedMetric} onChange={(e) => setSelectedMetric(e.target.value)}>
                {continuousColumns.map(col => (
                  <option key={col.name} value={col.name}>{col.name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={fetchAggregation}
              disabled={isAggregating || !groupBy || !selectedMetric}
              className={styles.aggregateButton}
            >
              {isAggregating ? 'Loading...' : 'Aggregate'}
            </button>
          </div>
        </section>

        {/* Chart */}
        {showAggregation && chartOptions && Highcharts && (
          <section className={styles.chartSection}>
            <h2>Visualization</h2>
            <div className={styles.chartContainer}>
              <HighchartsReact highcharts={Highcharts} options={chartOptions} />
            </div>
          </section>
        )}

        {/* Aggregation Results Table */}
        {showAggregation && aggregationResults.length > 0 && (
          <section className={styles.aggregationResultsSection}>
            <h2>Aggregation Results</h2>
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>{groupBy}</th>
                    <th>Min</th>
                    <th>Max</th>
                    <th>Average</th>
                  </tr>
                </thead>
                <tbody>
                  {aggregationResults.map((result, idx) => (
                    <tr key={idx}>
                      <td>{result.group_value}</td>
                      <td>{result.aggregations[selectedMetric]?.min?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                      <td>{result.aggregations[selectedMetric]?.max?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                      <td>{result.aggregations[selectedMetric]?.avg?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Raw Data Table */}
        <section className={styles.dataSection}>
          <h2>Raw Data</h2>

          {/* Search/Filter */}
          <div className={styles.tableControls}>
            <input
              type="text"
              placeholder="Search all columns..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className={styles.searchInput}
            />
          </div>

          {/* Table */}
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                {table.getHeaderGroups().map(headerGroup => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <th
                        key={header.id}
                        onClick={header.column.getToggleSortingHandler()}
                        className={header.column.getCanSort() ? styles.sortable : ''}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{
                          asc: ' ↑',
                          desc: ' ↓',
                        }[header.column.getIsSorted() as string] ?? ''}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className={styles.pagination}>
            <button
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
            >
              {'<<'}
            </button>
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              {'<'}
            </button>
            <span className={styles.pageInfo}>
              Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
            </span>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              {'>'}
            </button>
            <button
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
            >
              {'>>'}
            </button>
            <select
              value={table.getState().pagination.pageSize}
              onChange={(e) => table.setPageSize(Number(e.target.value))}
            >
              {[10, 20, 50, 100].map(pageSize => (
                <option key={pageSize} value={pageSize}>
                  Show {pageSize}
                </option>
              ))}
            </select>
          </div>
        </section>
      </main>
    </div>
  );
}

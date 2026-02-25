import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, CheckCircle, AlertTriangle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';

interface MetricsStripProps {
  onFilterChange: (status: string) => void;
  activeFilter: string;
}

interface PillConfig {
  key: string;
  label: string;
  icon: typeof FileText;
  colorIdle: string;
  colorActive: string;
  getValue: (statusCounts: Record<string, number>, total: number) => number;
}

const pills: PillConfig[] = [
  {
    key: '',
    label: 'Total',
    icon: FileText,
    colorIdle: 'bg-gray-100 text-gray-700 hover:bg-gray-200',
    colorActive: 'bg-gray-700 text-white ring-2 ring-gray-400 ring-offset-1',
    getValue: (_sc, total) => total,
  },
  {
    key: 'PROCESSED',
    label: 'Processed',
    icon: CheckCircle,
    colorIdle: 'bg-green-50 text-green-700 hover:bg-green-100',
    colorActive: 'bg-green-600 text-white ring-2 ring-green-400 ring-offset-1',
    getValue: (sc) => sc['PROCESSED'] || 0,
  },
  {
    key: 'PENDING_REVIEW',
    label: 'Needs Review',
    icon: AlertTriangle,
    colorIdle: 'bg-amber-50 text-amber-700 hover:bg-amber-100',
    colorActive: 'bg-amber-600 text-white ring-2 ring-amber-400 ring-offset-1',
    getValue: (sc) => sc['PENDING_REVIEW'] || 0,
  },
  {
    key: 'FAILED',
    label: 'Failed',
    icon: XCircle,
    colorIdle: 'bg-red-50 text-red-700 hover:bg-red-100',
    colorActive: 'bg-red-600 text-white ring-2 ring-red-400 ring-offset-1',
    getValue: (sc) => sc['FAILED'] || 0,
  },
];

const STORAGE_KEY = 'metricsStrip';

export default function MetricsStrip({ onFilterChange, activeFilter }: MetricsStripProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === 'collapsed';
    } catch {
      return false;
    }
  });

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 10000,
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? 'collapsed' : 'expanded');
    } catch {
      // localStorage unavailable
    }
  }, [collapsed]);

  const statusCounts = metrics?.statusCounts || {};
  const totalDocuments = metrics?.totalDocuments || 0;

  return (
    <div className="flex items-center gap-2">
      {!collapsed && (
        <div className="flex items-center gap-2 flex-wrap">
          {pills.map((pill) => {
            const Icon = pill.icon;
            const count = pill.getValue(statusCounts, totalDocuments);
            const isActive = activeFilter === pill.key;

            return (
              <button
                key={pill.key}
                onClick={() => onFilterChange(pill.key)}
                className={clsx(
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                  isActive ? pill.colorActive : pill.colorIdle
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {pill.label}
                <span className="font-semibold">{count}</span>
              </button>
            );
          })}
        </div>
      )}

      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors flex-shrink-0"
        title={collapsed ? 'Show metrics' : 'Hide metrics'}
      >
        {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
      </button>
    </div>
  );
}

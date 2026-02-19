import { useState } from 'react';
import { ChevronDown, ChevronRight, Lock } from 'lucide-react';

interface GenericDataFieldsProps {
  data: Record<string, any>;
  depth?: number;
}

/**
 * Schema-driven data renderer that displays ANY document type's extracted data.
 * Walks the JSON structure and renders fields dynamically based on value types.
 * No hardcoded field names -- works for any plugin output.
 */
export default function GenericDataFields({ data, depth = 0 }: GenericDataFieldsProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  if (!data || typeof data !== 'object') return null;

  const toggle = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const entries = Object.entries(data).filter(
    ([_, v]) => v !== null && v !== undefined && v !== ''
  );

  if (entries.length === 0) return <span className="text-gray-400 text-xs">No data</span>;

  return (
    <div className={depth > 0 ? 'pl-3 border-l border-gray-200 ml-1' : 'space-y-1'}>
      {entries.map(([key, value]) => {
        const label = formatLabel(key);

        // Skip internal/metadata keys
        if (key.startsWith('_') || key === 'version') return null;

        // Null
        if (value === null || value === undefined) return null;

        // Boolean
        if (typeof value === 'boolean') {
          return (
            <div key={key} className="flex items-center gap-2 py-0.5">
              <span className="text-gray-500 text-xs">{label}:</span>
              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                value ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
              }`}>
                {value ? 'Yes' : 'No'}
              </span>
            </div>
          );
        }

        // Number
        if (typeof value === 'number') {
          const formatted = isProbablyCurrency(key, value)
            ? `$${value.toLocaleString()}`
            : isProbablyPercentage(key, value)
            ? `${(value * 100).toFixed(2)}%`
            : value.toLocaleString();
          return (
            <div key={key} className="flex items-center gap-2 py-0.5">
              <span className="text-gray-500 text-xs">{label}:</span>
              <span className="text-gray-900 text-sm font-medium">{formatted}</span>
            </div>
          );
        }

        // String
        if (typeof value === 'string') {
          const masked = /\*{2,}/.test(value);
          return (
            <div key={key} className="flex items-start gap-2 py-0.5">
              <span className="text-gray-500 text-xs whitespace-nowrap">{label}:</span>
              <span className="text-gray-900 text-sm">
                {value}
                {masked && <Lock className="inline w-3 h-3 ml-1 text-gray-400" />}
              </span>
            </div>
          );
        }

        // Array
        if (Array.isArray(value)) {
          if (value.length === 0) return null;

          // Array of strings
          if (typeof value[0] === 'string') {
            return (
              <div key={key} className="py-0.5">
                <span className="text-gray-500 text-xs">{label}:</span>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {value.map((item, i) => (
                    <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            );
          }

          // Array of objects (beneficial owners, facilities, etc.)
          return (
            <div key={key} className="py-1">
              <button
                onClick={() => toggle(key)}
                className="flex items-center gap-1 text-gray-700 text-xs font-medium hover:text-gray-900"
              >
                {collapsed.has(key) ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                {label} ({value.length})
              </button>
              {!collapsed.has(key) && (
                <div className="mt-1 space-y-2">
                  {value.map((item, i) => (
                    <div key={i} className="border border-gray-200 rounded p-2 bg-white">
                      <div className="text-xs text-gray-400 mb-1">
                        {getItemTitle(item, i)}
                      </div>
                      <GenericDataFields data={item} depth={depth + 1} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        }

        // Nested object
        if (typeof value === 'object') {
          return (
            <div key={key} className="py-1">
              <button
                onClick={() => toggle(key)}
                className="flex items-center gap-1 text-gray-700 text-xs font-medium hover:text-gray-900"
              >
                {collapsed.has(key) ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                {label}
              </button>
              {!collapsed.has(key) && (
                <GenericDataFields data={value} depth={depth + 1} />
              )}
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}

/** Convert camelCase/snake_case to readable labels */
function formatLabel(key: string): string {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/_/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim();
}

function isProbablyCurrency(key: string, value: number): boolean {
  const currencyKeys = ['amount', 'cost', 'fee', 'payment', 'principal', 'limit', 'commitment', 'sublimit'];
  return value > 100 && currencyKeys.some((k) => key.toLowerCase().includes(k));
}

function isProbablyPercentage(key: string, value: number): boolean {
  const pctKeys = ['rate', 'percentage', 'ratio', 'spread', 'margin', 'floor', 'ceiling'];
  return value < 1 && value > 0 && pctKeys.some((k) => key.toLowerCase().includes(k));
}

function getItemTitle(item: any, index: number): string {
  // Try common name fields
  const name = item.fullName || item.name || item.lenderName || item.facilityName || item.factor;
  if (name) return `${name}`;
  return `Item ${index + 1}`;
}

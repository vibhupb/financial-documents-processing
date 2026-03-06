import { FileText, BarChart3, Code, Shield } from 'lucide-react';
import clsx from 'clsx';

export type DataViewTab = 'summary' | 'extracted' | 'json' | 'compliance';

interface DataViewTabsProps {
  activeTab: DataViewTab;
  onTabChange: (tab: DataViewTab) => void;
  hasTree?: boolean;
  hasExtractedData?: boolean;
  processingMode?: 'extract' | 'understand' | 'both';
  className?: string;
}

const tabs: { id: DataViewTab; label: string; icon: typeof FileText }[] = [
  { id: 'summary', label: 'Summary', icon: FileText },
  { id: 'extracted', label: 'Extracted', icon: BarChart3 },
  { id: 'json', label: 'JSON', icon: Code },
  { id: 'compliance', label: 'Compliance', icon: Shield },
];

export default function DataViewTabs({
  activeTab,
  onTabChange,
  hasTree,
  hasExtractedData,
  processingMode,
  className,
}: DataViewTabsProps) {
  // Filter tabs based on processingMode
  const visibleTabs = tabs.filter(({ id }) => {
    if (!processingMode || processingMode === 'both') return true;
    if (processingMode === 'extract') {
      // Show: extracted, json, summary (if tree available). Hide: compliance
      return id !== 'compliance';
    }
    if (processingMode === 'understand') {
      // Show: summary, compliance. Hide: extracted, json
      return id === 'summary' || id === 'compliance';
    }
    return true;
  });

  return (
    <div className={clsx('flex border-b border-gray-200 bg-white', className)}>
      {visibleTabs.map(({ id, label, icon: Icon }) => {
        const isActive = activeTab === id;
        const isDisabled = id === 'summary' && !hasTree;

        return (
          <button
            key={id}
            onClick={() => !isDisabled && onTabChange(id)}
            disabled={isDisabled}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors relative',
              isActive
                ? 'text-primary-600'
                : isDisabled
                  ? 'text-gray-300 cursor-not-allowed'
                  : 'text-gray-500 hover:text-gray-700',
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
            {id === 'extracted' && !hasExtractedData && (
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" title="Not yet extracted" />
            )}
            {/* Active indicator */}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600" />
            )}
          </button>
        );
      })}
    </div>
  );
}

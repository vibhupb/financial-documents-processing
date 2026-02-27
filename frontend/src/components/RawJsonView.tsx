import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import clsx from 'clsx';

interface RawJsonViewProps {
  data: unknown;
  label?: string;
  className?: string;
}

export default function RawJsonView({ data, label, className }: RawJsonViewProps) {
  const [copied, setCopied] = useState(false);

  const jsonStr = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonStr);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = jsonStr;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!data) {
    return (
      <div className={clsx('flex items-center justify-center h-full text-gray-400', className)}>
        <p>No data available</p>
      </div>
    );
  }

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
        <span className="text-sm font-medium text-gray-600">
          {'{ }'} {label || 'Raw JSON'}
        </span>
        <button
          onClick={handleCopy}
          className={clsx(
            'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors',
            copied
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          )}
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5" />
              Copied
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* JSON Content */}
      <div className="flex-1 overflow-auto p-4 bg-gray-900">
        <pre className="text-sm font-mono text-green-400 whitespace-pre-wrap break-words">
          {jsonStr}
        </pre>
      </div>
    </div>
  );
}

import { Lock } from 'lucide-react';

interface PIIIndicatorProps {
  value: string | undefined | null;
  isMasked: boolean;
}

/**
 * Displays a PII field value with a lock icon when masked.
 * The backend returns already-masked values for non-Admin users.
 */
export default function PIIIndicator({ value, isMasked }: PIIIndicatorProps) {
  if (!value) return <span className="text-sm text-gray-400">-</span>;

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-sm text-gray-900 font-mono">{value}</span>
      {isMasked && (
        <span title="PII field — masked for security">
          <Lock className="w-3.5 h-3.5 text-gray-400" />
        </span>
      )}
    </span>
  );
}

import clsx from 'clsx';
import type { ProcessingStatus, ReviewStatus } from '../types';

interface StatusBadgeProps {
  status: ProcessingStatus | ReviewStatus;
}

const statusConfig: Record<ProcessingStatus | ReviewStatus, { label: string; className: string }> = {
  // Processing statuses
  PENDING: { label: 'Pending', className: 'bg-gray-100 text-gray-700' },
  CLASSIFIED: { label: 'Classified', className: 'bg-blue-100 text-blue-700' },
  EXTRACTING: { label: 'Extracting', className: 'bg-yellow-100 text-yellow-700' },
  EXTRACTED: { label: 'Extracted', className: 'bg-indigo-100 text-indigo-700' },
  NORMALIZING: { label: 'Normalizing', className: 'bg-purple-100 text-purple-700' },
  PROCESSED: { label: 'Processed', className: 'bg-green-100 text-green-700' },
  REPROCESSING: { label: 'Reprocessing', className: 'bg-orange-100 text-orange-700' },
  FAILED: { label: 'Failed', className: 'bg-red-100 text-red-700' },
  SKIPPED: { label: 'Skipped', className: 'bg-gray-100 text-gray-500' },
  // Review statuses
  PENDING_REVIEW: { label: 'Pending Review', className: 'bg-amber-100 text-amber-700' },
  APPROVED: { label: 'Approved', className: 'bg-green-100 text-green-700' },
  REJECTED: { label: 'Rejected', className: 'bg-red-100 text-red-700' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.PENDING;

  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        config.className
      )}
    >
      {config.label}
    </span>
  );
}

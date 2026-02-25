import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, X, RotateCcw, Send } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface InlineReviewActionsProps {
  documentId: string;
  status: string;
  reviewStatus?: string;
  compact?: boolean;
  onActionComplete?: () => void;
}

export default function InlineReviewActions({
  documentId,
  status,
  reviewStatus,
  compact = false,
  onActionComplete,
}: InlineReviewActionsProps) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const reviewerEmail = user?.email || 'unknown';

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['documents'] });
    queryClient.invalidateQueries({ queryKey: ['document'] });
    queryClient.invalidateQueries({ queryKey: ['metrics'] });
    onActionComplete?.();
  };

  const approveMutation = useMutation({
    mutationFn: () =>
      api.approveDocument(documentId, { reviewedBy: reviewerEmail }),
    onSuccess: invalidateAll,
  });

  const rejectMutation = useMutation({
    mutationFn: (notes: string) =>
      api.rejectDocument(documentId, { reviewedBy: reviewerEmail, notes }),
    onSuccess: () => {
      setShowRejectInput(false);
      setRejectReason('');
      invalidateAll();
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: () => api.reprocessDocument(documentId),
    onSuccess: invalidateAll,
  });

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const isLoading =
    approveMutation.isPending || rejectMutation.isPending || reprocessMutation.isPending;

  // Show reprocess button for failed documents
  if (status === 'FAILED') {
    return (
      <div onClick={handleClick} className="inline-flex items-center">
        <button
          onClick={() => reprocessMutation.mutate()}
          disabled={isLoading}
          className={clsx(
            'inline-flex items-center gap-1.5 rounded-md font-medium transition-colors',
            'bg-orange-50 text-orange-700 hover:bg-orange-100 disabled:opacity-50',
            compact ? 'p-1.5' : 'px-3 py-1.5 text-xs'
          )}
          title="Reprocess"
        >
          <RotateCcw className={clsx('flex-shrink-0', compact ? 'w-3.5 h-3.5' : 'w-3.5 h-3.5')} />
          {!compact && 'Reprocess'}
        </button>
      </div>
    );
  }

  // Show approve/reject for pending review
  if (reviewStatus !== 'PENDING_REVIEW') {
    return null;
  }

  return (
    <div onClick={handleClick} className="inline-flex items-center gap-1.5">
      {/* Approve button — one-click */}
      <button
        onClick={() => approveMutation.mutate()}
        disabled={isLoading}
        className={clsx(
          'inline-flex items-center gap-1.5 rounded-md font-medium transition-colors',
          'bg-green-50 text-green-700 hover:bg-green-100 disabled:opacity-50',
          compact ? 'p-1.5' : 'px-3 py-1.5 text-xs'
        )}
        title="Approve"
      >
        <Check className={clsx('flex-shrink-0', compact ? 'w-3.5 h-3.5' : 'w-3.5 h-3.5')} />
        {!compact && 'Approve'}
      </button>

      {/* Reject button — expands to show reason input */}
      {!showRejectInput ? (
        <button
          onClick={() => setShowRejectInput(true)}
          disabled={isLoading}
          className={clsx(
            'inline-flex items-center gap-1.5 rounded-md font-medium transition-colors',
            'bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50',
            compact ? 'p-1.5' : 'px-3 py-1.5 text-xs'
          )}
          title="Reject"
        >
          <X className={clsx('flex-shrink-0', compact ? 'w-3.5 h-3.5' : 'w-3.5 h-3.5')} />
          {!compact && 'Reject'}
        </button>
      ) : (
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Reason..."
            className="text-xs border border-red-200 rounded-md px-2 py-1.5 w-40 focus:outline-none focus:ring-1 focus:ring-red-400"
            autoFocus
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === 'Enter' && rejectReason.trim()) {
                rejectMutation.mutate(rejectReason.trim());
              }
              if (e.key === 'Escape') {
                setShowRejectInput(false);
                setRejectReason('');
              }
            }}
          />
          <button
            onClick={() => {
              if (rejectReason.trim()) {
                rejectMutation.mutate(rejectReason.trim());
              }
            }}
            disabled={!rejectReason.trim() || isLoading}
            className="p-1.5 rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            title="Send rejection"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => {
              setShowRejectInput(false);
              setRejectReason('');
            }}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 transition-colors"
            title="Cancel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

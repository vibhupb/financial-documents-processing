import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

interface Props {
  documentId: string;
  reportId: string;
  requirementId: string;
  currentVerdict: string;
  onClose: () => void;
}

const VERDICTS = ['PASS', 'FAIL', 'PARTIAL', 'NOT_FOUND'];

export default function ReviewerOverride({
  documentId,
  reportId,
  requirementId,
  currentVerdict,
  onClose,
}: Props) {
  const [verdict, setVerdict] = useState(currentVerdict);
  const [note, setNote] = useState('');
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api.submitComplianceReview(documentId, reportId, {
        overrides: [
          {
            requirementId,
            correctedVerdict: verdict,
            reviewerNote: note,
          },
        ],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compliance'] });
      onClose();
    },
  });
  return (
    <div className="border rounded p-3 bg-gray-50 mt-2 space-y-2">
      <div className="flex gap-2">
        {VERDICTS.map((v) => (
          <button
            key={v}
            onClick={() => setVerdict(v)}
            className={`px-2 py-1 text-xs rounded ${
              v === verdict
                ? 'bg-primary-600 text-white'
                : 'bg-white border'
            }`}
          >
            {v}
          </button>
        ))}
      </div>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Explain the correction..."
        className="w-full border rounded p-2 text-sm h-16"
      />
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          className="btn-primary text-xs px-3 py-1"
        >
          Submit
        </button>
        <button onClick={onClose} className="text-xs text-gray-500">
          Cancel
        </button>
      </div>
    </div>
  );
}

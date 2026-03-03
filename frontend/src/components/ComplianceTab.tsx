import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import VerdictBadge from './VerdictBadge';
import ComplianceScoreGauge from './ComplianceScoreGauge';

interface Props {
  documentId: string;
  onPageClick?: (page: number) => void;
}

export default function ComplianceTab({ documentId, onPageClick }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['compliance', documentId],
    queryFn: () => api.getComplianceReports(documentId),
  });
  if (isLoading)
    return <div className="p-4 text-gray-500">Loading compliance...</div>;
  const reports = data?.reports || [];
  if (!reports.length)
    return <div className="p-4 text-gray-400">No compliance reports.</div>;
  const report = reports[0]; // most recent
  return (
    <div className="p-4 overflow-auto space-y-4">
      <ComplianceScoreGauge score={report.overallScore} />
      <div className="space-y-2">
        {(report.results || []).map((r: any) => (
          <div key={r.requirementId} className="border rounded p-3 bg-white">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{r.requirementId}</span>
              <VerdictBadge verdict={r.reviewerOverride || r.verdict} />
            </div>
            {r.evidence && (
              <p
                className="text-xs text-gray-600 mt-1 cursor-pointer hover:text-primary-600"
                onClick={() =>
                  r.pageReferences?.[0] && onPageClick?.(r.pageReferences[0])
                }
                title={
                  r.evidenceCharStart != null
                    ? `Chars ${r.evidenceCharStart}–${r.evidenceCharEnd} on page ${r.pageReferences?.[0]}`
                    : undefined
                }
              >
                <span className="bg-yellow-100 px-0.5 rounded">
                  {r.evidence}
                </span>
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

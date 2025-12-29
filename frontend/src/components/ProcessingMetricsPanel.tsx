import { useState } from 'react';
import {
  DollarSign,
  Clock,
  ChevronDown,
  ChevronRight,
  Cpu,
  Zap,
  FileText,
  Brain,
} from 'lucide-react';
import clsx from 'clsx';
import type { ProcessingCost, ProcessingTime } from '../types';

interface ProcessingMetricsPanelProps {
  processingCost?: ProcessingCost;
  processingTime?: ProcessingTime;
  className?: string;
}

export default function ProcessingMetricsPanel({
  processingCost,
  processingTime,
  className,
}: ProcessingMetricsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!processingCost && !processingTime) {
    return null;
  }

  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTime = (seconds: number) => {
    if (seconds < 1) return '<1s';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
  };

  return (
    <div className={clsx('border border-gray-200 rounded-lg overflow-hidden bg-white', className)}>
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 bg-gradient-to-r from-blue-50 to-purple-50 hover:from-blue-100 hover:to-purple-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Cpu className="w-5 h-5 text-blue-600" />
          <span className="font-semibold text-gray-900">Processing Metrics</span>
        </div>
        <div className="flex items-center gap-4">
          {/* Summary in collapsed state */}
          {processingCost && (
            <span className="text-sm font-medium text-green-600">
              {formatCost(processingCost.totalCost)}
            </span>
          )}
          {processingTime && (
            <span className="text-sm font-medium text-blue-600">
              {processingTime.totalSeconds > 0 ? formatTime(processingTime.totalSeconds) : '—'}
            </span>
          )}
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* Cost Breakdown */}
          {processingCost?.breakdown && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                <DollarSign className="w-3.5 h-3.5" />
                Cost Breakdown ({processingCost.currency})
              </h4>

              <div className="space-y-2">
                {/* Router (Claude 3 Haiku) */}
                {processingCost.breakdown.router && (
                  <CostRow
                    icon={<Brain className="w-4 h-4 text-purple-500" />}
                    label="Router"
                    sublabel={processingCost.breakdown.router.model}
                    cost={processingCost.breakdown.router.cost}
                    details={[
                      `${processingCost.breakdown.router.inputTokens.toLocaleString()} input tokens`,
                      `${processingCost.breakdown.router.outputTokens.toLocaleString()} output tokens`,
                    ]}
                  />
                )}

                {/* Textract */}
                {processingCost.breakdown.textract && (
                  <CostRow
                    icon={<FileText className="w-4 h-4 text-orange-500" />}
                    label="Textract"
                    sublabel="OCR & Extraction"
                    cost={processingCost.breakdown.textract.cost}
                    details={[
                      `${processingCost.breakdown.textract.pages} pages`,
                      `$${processingCost.breakdown.textract.costPerPage}/page`,
                    ]}
                  />
                )}

                {/* Normalizer (Claude 3.5 Haiku) */}
                {processingCost.breakdown.normalizer && (
                  <CostRow
                    icon={<Zap className="w-4 h-4 text-green-500" />}
                    label="Normalizer"
                    sublabel={processingCost.breakdown.normalizer.model}
                    cost={processingCost.breakdown.normalizer.cost}
                    details={[
                      `${processingCost.breakdown.normalizer.inputTokens.toLocaleString()} input tokens`,
                      `${processingCost.breakdown.normalizer.outputTokens.toLocaleString()} output tokens`,
                    ]}
                  />
                )}

                {/* Step Functions */}
                {processingCost.breakdown.stepFunctions && (
                  <CostRow
                    icon={<Cpu className="w-4 h-4 text-blue-500" />}
                    label="Step Functions"
                    sublabel="Orchestration"
                    cost={processingCost.breakdown.stepFunctions.cost}
                    details={[
                      `${processingCost.breakdown.stepFunctions.stateTransitions} state transitions`,
                    ]}
                  />
                )}

                {/* Lambda */}
                {processingCost.breakdown.lambda && (
                  <CostRow
                    icon={<Cpu className="w-4 h-4 text-yellow-500" />}
                    label="Lambda"
                    sublabel="Compute"
                    cost={processingCost.breakdown.lambda.cost}
                    details={[
                      `${processingCost.breakdown.lambda.invocations} invocations`,
                      `${processingCost.breakdown.lambda.gbSeconds}GB-s`,
                    ]}
                  />
                )}

                {/* Total */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-200 mt-2">
                  <span className="font-semibold text-gray-900">Total Cost</span>
                  <span className="text-lg font-bold text-green-600">
                    {formatCost(processingCost.totalCost)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Time Breakdown */}
          {processingTime?.breakdown && (
            <div className="pt-3 border-t border-gray-100">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" />
                Processing Time
              </h4>

              {processingTime.totalSeconds > 0 ? (
                <div className="space-y-2">
                  {/* Router Time */}
                  {processingTime.breakdown.router && (
                    <TimeRow
                      icon={<Brain className="w-4 h-4 text-purple-500" />}
                      label="Router"
                      description={processingTime.breakdown.router.description}
                      seconds={processingTime.breakdown.router.estimatedSeconds}
                      totalSeconds={processingTime.totalSeconds}
                    />
                  )}

                  {/* Textract Time */}
                  {processingTime.breakdown.textract && (
                    <TimeRow
                      icon={<FileText className="w-4 h-4 text-orange-500" />}
                      label="Textract"
                      description={`${processingTime.breakdown.textract.pages} pages`}
                      seconds={processingTime.breakdown.textract.estimatedSeconds}
                      totalSeconds={processingTime.totalSeconds}
                    />
                  )}

                  {/* Normalizer Time */}
                  {processingTime.breakdown.normalizer && (
                    <TimeRow
                      icon={<Zap className="w-4 h-4 text-green-500" />}
                      label="Normalizer"
                      description={processingTime.breakdown.normalizer.description}
                      seconds={processingTime.breakdown.normalizer.estimatedSeconds}
                      totalSeconds={processingTime.totalSeconds}
                    />
                  )}

                  {/* Total */}
                  <div className="flex items-center justify-between pt-2 border-t border-gray-200 mt-2">
                    <span className="font-semibold text-gray-900">Total Time</span>
                    <span className="text-lg font-bold text-blue-600">
                      {formatTime(processingTime.totalSeconds)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-500 italic py-2">
                  Timing data unavailable (reprocessed document)
                </div>
              )}
            </div>
          )}

          {/* Timestamps */}
          {processingTime && (
            <div className="pt-3 border-t border-gray-100 text-xs text-gray-500">
              {processingTime.startedAt && (
                <div className="flex justify-between">
                  <span>Started:</span>
                  <span>{new Date(processingTime.startedAt).toLocaleString()}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Completed:</span>
                <span>{new Date(processingTime.completedAt).toLocaleString()}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Cost row component
function CostRow({
  icon,
  label,
  sublabel,
  cost,
  details,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel: string;
  cost: number;
  details: string[];
}) {
  return (
    <div className="flex items-start justify-between py-2 px-2 bg-gray-50 rounded-lg">
      <div className="flex items-start gap-2">
        <div className="mt-0.5">{icon}</div>
        <div>
          <div className="font-medium text-gray-900 text-sm">{label}</div>
          <div className="text-xs text-gray-500">{sublabel}</div>
          <div className="text-xs text-gray-400 mt-0.5">
            {details.join(' • ')}
          </div>
        </div>
      </div>
      <div className="text-sm font-medium text-gray-900">
        ${cost.toFixed(4)}
      </div>
    </div>
  );
}

// Time row component with progress bar
function TimeRow({
  icon,
  label,
  description,
  seconds,
  totalSeconds,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  seconds: number;
  totalSeconds: number;
}) {
  const percentage = totalSeconds > 0 ? (seconds / totalSeconds) * 100 : 0;

  const formatTime = (s: number) => {
    if (s < 1) return '<1s';
    if (s < 60) return `${s.toFixed(1)}s`;
    return `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;
  };

  return (
    <div className="py-2 px-2 bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium text-gray-900 text-sm">{label}</span>
          <span className="text-xs text-gray-500">({description})</span>
        </div>
        <span className="text-sm font-medium text-gray-900">{formatTime(seconds)}</span>
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

import { CheckCircle, Loader2, Circle, XCircle, Search, FileText, Sparkles, Shield } from 'lucide-react';
import clsx from 'clsx';
import type { StageInfo } from '../types';

interface PipelineTrackerProps {
  stages: {
    classification: StageInfo;
    extraction: StageInfo;
    normalization: StageInfo;
    compliance?: StageInfo;
  };
}

interface StageConfig {
  key: string;
  label: string;
  icon: typeof Search;
}

const baseStageConfigs: StageConfig[] = [
  { key: 'classification', label: 'Classification', icon: Search },
  { key: 'extraction', label: 'Extraction', icon: FileText },
  { key: 'normalization', label: 'Normalization', icon: Sparkles },
];

const complianceStageConfig: StageConfig = {
  key: 'compliance', label: 'Compliance', icon: Shield,
};

function getStatusIcon(status: StageInfo['status']) {
  switch (status) {
    case 'COMPLETED':
      return <CheckCircle className="w-7 h-7 text-green-600" />;
    case 'IN_PROGRESS':
      return (
        <div className="relative">
          <div className="absolute inset-0 w-7 h-7 rounded-full bg-primary-400 opacity-30 animate-ping" />
          <Loader2 className="w-7 h-7 text-primary-600 animate-spin" />
        </div>
      );
    case 'FAILED':
      return <XCircle className="w-7 h-7 text-red-600" />;
    case 'PENDING':
    default:
      return <Circle className="w-7 h-7 text-gray-300" />;
  }
}

function formatElapsed(seconds: number): string {
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function getDetailText(stage: StageInfo): string {
  if (stage.status === 'COMPLETED' && stage.elapsed != null) {
    return formatElapsed(stage.elapsed);
  }
  if (stage.status === 'IN_PROGRESS' && stage.progress) {
    const { completed, total, currentSection } = stage.progress;
    const progressText = total != null ? `${completed}/${total} sections` : `${completed} done`;
    return currentSection ? `${progressText} - ${currentSection}` : progressText;
  }
  if (stage.status === 'FAILED') {
    return 'Failed';
  }
  return '';
}

export default function PipelineTracker({ stages }: PipelineTrackerProps) {
  // Build stage list — include compliance only when the backend sends it
  const stageConfigs = stages.compliance
    ? [...baseStageConfigs, complianceStageConfig]
    : baseStageConfigs;

  const stageMap: Record<string, StageInfo> = {
    classification: stages.classification,
    extraction: stages.extraction,
    normalization: stages.normalization,
    ...(stages.compliance ? { compliance: stages.compliance } : {}),
  };

  return (
    <div className="flex items-center gap-0 flex-wrap">
      {stageConfigs.map((config, index) => {
        const stage = stageMap[config.key];
        if (!stage) return null;
        const isPending = stage.status === 'PENDING';
        const isCompleted = stage.status === 'COMPLETED';
        const detail = getDetailText(stage);

        const showLineBefore = index > 0;
        const prevKey = index > 0 ? stageConfigs[index - 1].key : null;
        const prevStage = prevKey ? stageMap[prevKey] : null;
        const prevCompleted = prevStage?.status === 'COMPLETED';

        return (
          <div key={config.key} className="flex items-center">
            {showLineBefore && (
              <div
                className={clsx(
                  'w-10 h-1 rounded-full flex-shrink-0 transition-colors duration-500',
                  prevCompleted ? 'bg-green-400' : 'bg-gray-200'
                )}
              />
            )}

            <div
              className={clsx(
                'flex items-center gap-2.5 px-3 py-2 rounded-lg transition-all duration-300',
                isPending && 'opacity-40',
                stage.status === 'IN_PROGRESS' && 'bg-primary-50 ring-1 ring-primary-200'
              )}
            >
              {getStatusIcon(stage.status)}
              <div className="min-w-0">
                <p
                  className={clsx(
                    'text-sm font-semibold whitespace-nowrap',
                    isPending ? 'text-gray-400' : 'text-gray-900'
                  )}
                >
                  {config.label}
                </p>
                {detail && (
                  <p
                    className={clsx(
                      'text-sm whitespace-nowrap',
                      isCompleted ? 'text-green-600 font-medium' : 'text-gray-500'
                    )}
                  >
                    {detail}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

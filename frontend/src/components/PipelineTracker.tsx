import { CheckCircle, Loader2, Circle, XCircle, Search, FileText, Sparkles } from 'lucide-react';
import clsx from 'clsx';
import type { StageInfo } from '../types';

interface PipelineTrackerProps {
  stages: {
    classification: StageInfo;
    extraction: StageInfo;
    normalization: StageInfo;
  };
}

interface StageConfig {
  key: keyof PipelineTrackerProps['stages'];
  label: string;
  icon: typeof Search;
}

const stageConfigs: StageConfig[] = [
  { key: 'classification', label: 'Classification', icon: Search },
  { key: 'extraction', label: 'Extraction', icon: FileText },
  { key: 'normalization', label: 'Normalization', icon: Sparkles },
];

function getStatusIcon(status: StageInfo['status']) {
  switch (status) {
    case 'COMPLETED':
      return <CheckCircle className="w-5 h-5 text-green-600" />;
    case 'IN_PROGRESS':
      return <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />;
    case 'FAILED':
      return <XCircle className="w-5 h-5 text-red-600" />;
    case 'PENDING':
    default:
      return <Circle className="w-5 h-5 text-gray-300" />;
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
  return (
    <div className="flex items-center gap-0">
      {stageConfigs.map((config, index) => {
        const stage = stages[config.key];
        const isPending = stage.status === 'PENDING';
        const isCompleted = stage.status === 'COMPLETED';
        const detail = getDetailText(stage);

        // Show connecting line before all stages except the first
        const showLineBefore = index > 0;
        const prevStage = index > 0 ? stages[stageConfigs[index - 1].key] : null;
        const prevCompleted = prevStage?.status === 'COMPLETED';

        return (
          <div key={config.key} className="flex items-center">
            {/* Connecting line */}
            {showLineBefore && (
              <div
                className={clsx(
                  'w-8 h-0.5 flex-shrink-0',
                  prevCompleted ? 'bg-green-400' : 'bg-gray-200'
                )}
              />
            )}

            {/* Stage node */}
            <div
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors',
                isPending && 'opacity-50'
              )}
            >
              {getStatusIcon(stage.status)}
              <div className="min-w-0">
                <p
                  className={clsx(
                    'text-xs font-medium whitespace-nowrap',
                    isPending ? 'text-gray-400' : 'text-gray-900'
                  )}
                >
                  {config.label}
                </p>
                {detail && (
                  <p
                    className={clsx(
                      'text-xs whitespace-nowrap',
                      isCompleted ? 'text-green-600' : 'text-gray-500'
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

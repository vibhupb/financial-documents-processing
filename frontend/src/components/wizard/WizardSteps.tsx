import { CheckCircle } from 'lucide-react';
import clsx from 'clsx';

interface Step {
  id: number;
  name: string;
}

const steps: Step[] = [
  { id: 1, name: 'Upload Sample' },
  { id: 2, name: 'Review Fields' },
  { id: 3, name: 'Configure' },
  { id: 4, name: 'Save' },
];

export default function WizardSteps({ current }: { current: number }) {
  return (
    <nav className="flex items-center justify-between mb-8">
      {steps.map((step, i) => {
        const done = current > step.id;
        const active = current === step.id;
        return (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex items-center gap-2">
              <div
                className={clsx(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
                  done && 'bg-green-100 text-green-700',
                  active && 'bg-primary-600 text-white',
                  !done && !active && 'bg-gray-100 text-gray-400'
                )}
              >
                {done ? <CheckCircle className="w-5 h-5" /> : step.id}
              </div>
              <span
                className={clsx(
                  'text-sm font-medium',
                  active ? 'text-gray-900' : 'text-gray-400'
                )}
              >
                {step.name}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={clsx(
                  'flex-1 h-0.5 mx-4',
                  done ? 'bg-green-300' : 'bg-gray-200'
                )}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}

import { ReactNode } from 'react';
import clsx from 'clsx';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
}

export default function MetricCard({ title, value, icon, trend, className }: MetricCardProps) {
  return (
    <div className={clsx('card', className)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">{value}</p>
          {trend && (
            <p
              className={clsx(
                'mt-1 text-sm',
                trend.isPositive ? 'text-green-600' : 'text-red-600'
              )}
            >
              {trend.isPositive ? '+' : '-'}
              {Math.abs(trend.value)}% from last week
            </p>
          )}
        </div>
        <div className="w-12 h-12 bg-primary-50 rounded-lg flex items-center justify-center text-primary-600">
          {icon}
        </div>
      </div>
    </div>
  );
}

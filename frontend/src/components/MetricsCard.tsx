'use client';

interface MetricsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon?: React.ReactNode;
}

export default function MetricsCard({
  title,
  value,
  subtitle,
  trend = 'neutral',
  icon,
}: MetricsCardProps) {
  const trendColors = {
    up: 'text-green-600 dark:text-green-400',
    down: 'text-red-600 dark:text-red-400',
    neutral: 'text-gray-600 dark:text-gray-400',
  };

  const bgColors = {
    up: 'bg-green-50 dark:bg-green-900/20',
    down: 'bg-red-50 dark:bg-red-900/20',
    neutral: 'bg-white dark:bg-gray-800',
  };

  return (
    <div className={`${bgColors[trend]} p-6 rounded-lg shadow-md border border-gray-200 dark:border-gray-700`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </p>
          <p className={`text-3xl font-bold mt-2 ${trendColors[trend]}`}>
            {value}
          </p>
          {subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {subtitle}
            </p>
          )}
        </div>
        {icon && (
          <div className="flex-shrink-0 ml-4 text-gray-400 dark:text-gray-500">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}


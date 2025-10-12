'use client';

interface Signal {
  id?: number;
  symbol: string;
  timeframe: string;
  direction: 'BUY' | 'SELL' | 'HOLD';
  prob: number;
  created_at: string;
  exchange?: string;
}

interface SignalsTableProps {
  signals: Signal[];
  loading?: boolean;
}

export default function SignalsTable({ signals, loading = false }: SignalsTableProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-center text-gray-500">Загрузка сигналов...</div>
      </div>
    );
  }

  if (!signals || signals.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          Нет недавних сигналов
        </div>
      </div>
    );
  }

  const getDirectionColor = (direction: string) => {
    switch (direction) {
      case 'BUY':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'SELL':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
    }
  };

  const getProbabilityColor = (prob: number) => {
    if (prob >= 0.7) return 'text-green-600 dark:text-green-400 font-bold';
    if (prob >= 0.6) return 'text-green-500 dark:text-green-500';
    if (prob >= 0.5) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-gray-600 dark:text-gray-400';
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-700">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              Время
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              Пара
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              TF
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              Сигнал
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
              Вероятность
            </th>
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
          {signals.map((signal, idx) => (
            <tr key={signal.id || idx} className="hover:bg-gray-50 dark:hover:bg-gray-700">
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                {new Date(signal.created_at).toLocaleString('ru-RU', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                {signal.symbol}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                {signal.timeframe}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getDirectionColor(signal.direction)}`}>
                  {signal.direction}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                <span className={getProbabilityColor(signal.prob)}>
                  {(signal.prob * 100).toFixed(1)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


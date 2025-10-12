'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import SignalsTable from '@/components/SignalsTable';

export default function Signals() {
  const { data: signals, isLoading: signalsLoading } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getRecentSignals(50),
    refetchInterval: 30000,
  });

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          🔔 Торговые Сигналы
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Все рекомендации ИИ для покупки и продажи
        </p>
      </header>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
        <SignalsTable signals={signals?.data || []} loading={signalsLoading} />
      </div>
    </div>
  );
}

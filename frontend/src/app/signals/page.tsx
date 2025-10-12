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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50 dark:from-gray-900 dark:via-gray-900 dark:to-blue-900/20">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="px-6 py-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                🔔 Торговые Сигналы
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                Все рекомендации ИИ для покупки и продажи активов
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Обновлено: {new Date().toLocaleTimeString('ru-RU')}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm text-green-600 dark:text-green-400 font-medium">Обновление каждые 30 сек</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Все Сигналы
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Последние 50 торговых рекомендаций от искусственного интеллекта
            </p>
          </div>
          <SignalsTable signals={signals?.data || []} loading={signalsLoading} />
        </div>
      </div>
    </div>
  );
}

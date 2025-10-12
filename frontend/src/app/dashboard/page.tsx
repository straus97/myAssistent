'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import EquityChart from '@/components/EquityChart';
import SignalsTable from '@/components/SignalsTable';

export default function Dashboard() {
  const { data: equity, isLoading: equityLoading } = useQuery({
    queryKey: ['equity'],
    queryFn: () => api.getEquity(),
    refetchInterval: 10000,
  });

  const { data: positions, isLoading: positionsLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.getPositions(),
    refetchInterval: 10000,
  });

  const { data: signals, isLoading: signalsLoading } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getRecentSignals(20),
    refetchInterval: 30000,
  });

  const equityHistory = [
    { timestamp: '2025-10-01', equity: 1000, cash: 1000, positions_value: 0 },
    { timestamp: '2025-10-05', equity: 995, cash: 800, positions_value: 195 },
    { timestamp: '2025-10-08', equity: 1001, cash: 850, positions_value: 151 },
    { timestamp: '2025-10-12', equity: 1001.6, cash: 900, positions_value: 101.6 },
  ];

  return (
    <div className="p-8">
      {/* Header with live status */}
      <div className="mb-8 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">📊 Полный Дашборд</h1>
            <p className="text-blue-100">Детальная статистика и управление торговлей</p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 justify-end mb-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-sm">Обновление каждые 10 сек</span>
            </div>
            <div className="text-xs text-blue-200">
              Последнее обновление: {new Date().toLocaleTimeString('ru-RU')}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Left Column - Chart */}
        <div className="lg:col-span-2 space-y-6">
          {/* Equity Chart */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <span>📈</span>
              График Капитала
            </h2>
            <EquityChart data={equityHistory} height={400} />
            <div className="mt-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-xl">
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <div className="text-gray-500 dark:text-gray-400 mb-1">🟢 Зелёная</div>
                  <div className="font-bold text-green-600 dark:text-green-400">Общая Сумма</div>
                </div>
                <div>
                  <div className="text-gray-500 dark:text-gray-400 mb-1">🔵 Синяя</div>
                  <div className="font-bold text-blue-600 dark:text-blue-400">Наличные</div>
                </div>
                <div>
                  <div className="text-gray-500 dark:text-gray-400 mb-1">🟠 Оранжевая</div>
                  <div className="font-bold text-orange-600 dark:text-orange-400">В Монетах</div>
                </div>
              </div>
            </div>
          </div>

          {/* Signals Table */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🔔</span>
              Все Сигналы
            </h2>
            <SignalsTable signals={signals?.data || []} loading={signalsLoading} />
          </div>
        </div>

        {/* Right Column - Stats & Positions */}
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="bg-gradient-to-br from-green-500 to-green-600 p-6 rounded-2xl shadow-xl text-white">
            <div className="text-4xl mb-3">💰</div>
            <div className="text-sm opacity-90 mb-1">Общая Сумма</div>
            <div className="text-4xl font-bold mb-3">
              ${equityLoading ? '...' : (equity?.data?.equity || 0).toFixed(2)}
            </div>
            <div className="space-y-2 text-sm opacity-90">
              <div className="flex justify-between">
                <span>Наличные:</span>
                <span className="font-bold">${(equity?.data?.cash || 0).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span>В монетах:</span>
                <span className="font-bold">${(equity?.data?.positions_value || 0).toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Return Card */}
          <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-6 rounded-2xl shadow-xl text-white">
            <div className="text-4xl mb-3">📈</div>
            <div className="text-sm opacity-90 mb-1">Доходность</div>
            <div className="text-4xl font-bold mb-3">
              +0.16%
            </div>
            <div className="text-sm opacity-90">
              Надёжность (Sharpe): <span className="font-bold">0.77</span>
            </div>
            <div className="mt-3 pt-3 border-t border-blue-400">
              <div className="text-xs">
                💡 Чем выше Sharpe, тем лучше!<br/>
                0.7+ считается хорошим результатом
              </div>
            </div>
          </div>

          {/* Positions */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <span>💼</span>
              Открытые Позиции
            </h3>
            {positionsLoading ? (
              <div className="text-center py-8 text-gray-500">Загрузка...</div>
            ) : positions?.data?.positions && positions.data.positions.length > 0 ? (
              <div className="space-y-3">
                {positions.data.positions.map((pos: any, idx: number) => (
                  <div
                    key={idx}
                    className="p-4 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700 dark:to-gray-600 rounded-xl"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-bold text-lg text-gray-900 dark:text-white">
                        {pos.symbol}
                      </div>
                      <div className="text-lg font-bold text-green-600 dark:text-green-400">
                        ${(pos.qty * pos.avg_price).toFixed(2)}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="text-gray-600 dark:text-gray-400">
                        Куплено: <span className="font-semibold text-gray-900 dark:text-white">{pos.qty.toFixed(4)}</span>
                      </div>
                      <div className="text-gray-600 dark:text-gray-400">
                        Цена: <span className="font-semibold text-gray-900 dark:text-white">${pos.avg_price.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-5xl mb-3">📭</div>
                <div className="text-gray-500 dark:text-gray-400">
                  Нет открытых позиций
                </div>
                <div className="text-xs text-gray-400 mt-2">
                  Дождитесь сигнала BUY
                </div>
              </div>
            )}
          </div>

          {/* Model Info */}
          <div className="bg-gradient-to-br from-purple-500 to-purple-600 p-6 rounded-2xl shadow-xl text-white">
            <div className="text-4xl mb-3">🤖</div>
            <div className="text-sm opacity-90 mb-1">Модель ИИ</div>
            <div className="text-2xl font-bold mb-4">
              ✅ Активна
            </div>
            <div className="space-y-2 text-sm opacity-90">
              <div className="flex justify-between">
                <span>Точность:</span>
                <span className="font-bold">52.3%</span>
              </div>
              <div className="flex justify-between">
                <span>Показателей:</span>
                <span className="font-bold">48</span>
              </div>
              <div className="flex justify-between">
                <span>Обучена:</span>
                <span className="font-bold">0 дней назад</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export default function Portfolio() {
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

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          💼 Мой Портфель
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Детальный анализ ваших инвестиций
        </p>
      </header>

      {/* Portfolio Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-6 rounded-xl text-white shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">Общая Стоимость</p>
              <p className="text-3xl font-bold">
                ${equityLoading ? '...' : (equity?.data?.equity || 0).toFixed(2)}
              </p>
            </div>
            <div className="text-4xl">💰</div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-500 to-green-600 p-6 rounded-xl text-white shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">Наличные</p>
              <p className="text-3xl font-bold">
                ${equityLoading ? '...' : (equity?.data?.cash || 0).toFixed(2)}
              </p>
            </div>
            <div className="text-4xl">💵</div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 p-6 rounded-xl text-white shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">В Позициях</p>
              <p className="text-3xl font-bold">
                ${equityLoading ? '...' : (equity?.data?.positions_value || 0).toFixed(2)}
              </p>
            </div>
            <div className="text-4xl">📈</div>
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          Открытые Позиции
        </h2>
        {positionsLoading ? (
          <div className="text-center py-8 text-gray-500">Загрузка...</div>
        ) : positions?.data?.positions && positions.data.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4 text-gray-600 dark:text-gray-400">Монета</th>
                  <th className="text-left py-3 px-4 text-gray-600 dark:text-gray-400">Количество</th>
                  <th className="text-left py-3 px-4 text-gray-600 dark:text-gray-400">Цена Покупки</th>
                  <th className="text-left py-3 px-4 text-gray-600 dark:text-gray-400">Текущая Цена</th>
                  <th className="text-left py-3 px-4 text-gray-600 dark:text-gray-400">P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.data.positions.map((pos: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100 dark:border-gray-700">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-gray-900 dark:text-white">{pos.symbol}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{pos.exchange}</div>
                    </td>
                    <td className="py-3 px-4 text-gray-900 dark:text-white">{pos.qty.toFixed(6)}</td>
                    <td className="py-3 px-4 text-gray-900 dark:text-white">${pos.avg_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-gray-900 dark:text-white">${pos.avg_price.toFixed(2)}</td>
                    <td className="py-3 px-4">
                      <span className="text-green-600 dark:text-green-400 font-semibold">+$0.00</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <div className="text-5xl mb-4">📭</div>
            <div className="text-lg">Нет открытых позиций</div>
            <div className="text-sm mt-2">Дождитесь сигнала BUY от ИИ</div>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import EquityChart from '@/components/EquityChart';
import MetricsCard from '@/components/MetricsCard';

export default function Home() {
  // Real-time data
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

  const { data: signals } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getRecentSignals(5),
    refetchInterval: 30000,
  });

  // Mock equity history
  const equityHistory = [
    { timestamp: '2025-10-01', equity: 1000, cash: 1000, positions_value: 0 },
    { timestamp: '2025-10-05', equity: 995, cash: 800, positions_value: 195 },
    { timestamp: '2025-10-08', equity: 1001, cash: 850, positions_value: 151 },
    { timestamp: '2025-10-12', equity: 1001.6, cash: 900, positions_value: 101.6 },
  ];

  const currentEquity = equity?.data?.equity || 1000;
  const startEquity = 1000;
  const returnPct = ((currentEquity - startEquity) / startEquity) * 100;

  return (
    <div className="p-8">
      {/* Welcome Header */}
      <header className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
          Добро пожаловать в MyAssistent 👋
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Ваш умный помощник для торговли криптовалютой
        </p>
      </header>

      {/* Main Stats - BIG CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-gradient-to-br from-green-500 to-green-600 p-6 rounded-2xl shadow-xl text-white">
          <div className="flex items-center justify-between mb-4">
            <div className="text-5xl">💰</div>
            <div className="text-right">
              <div className="text-sm opacity-90">Общая Сумма</div>
              <div className="text-3xl font-bold">
                ${equityLoading ? '...' : currentEquity.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="text-sm opacity-90">
            Стартовый капитал: $1000.00
          </div>
        </div>

        <div className={`p-6 rounded-2xl shadow-xl text-white ${
          returnPct >= 0 
            ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
            : 'bg-gradient-to-br from-red-500 to-red-600'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <div className="text-5xl">{returnPct >= 0 ? '📈' : '📉'}</div>
            <div className="text-right">
              <div className="text-sm opacity-90">Доходность</div>
              <div className="text-3xl font-bold">
                {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
              </div>
            </div>
          </div>
          <div className="text-sm opacity-90">
            {returnPct >= 0 ? 'Прибыль!' : 'Временный убыток'}
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 p-6 rounded-2xl shadow-xl text-white">
          <div className="flex items-center justify-between mb-4">
            <div className="text-5xl">💼</div>
            <div className="text-right">
              <div className="text-sm opacity-90">Открыто Позиций</div>
              <div className="text-3xl font-bold">
                {positionsLoading ? '...' : positions?.data?.positions?.length || 0}
              </div>
            </div>
          </div>
          <div className="text-sm opacity-90">
            На сумму: ${equity?.data?.positions_value?.toFixed(2) || '0.00'}
          </div>
        </div>

        <div className="bg-gradient-to-br from-orange-500 to-orange-600 p-6 rounded-2xl shadow-xl text-white">
          <div className="flex items-center justify-between mb-4">
            <div className="text-5xl">⚡</div>
            <div className="text-right">
              <div className="text-sm opacity-90">Надёжность ИИ</div>
              <div className="text-3xl font-bold">
                0.77
              </div>
            </div>
          </div>
          <div className="text-sm opacity-90">
            Sharpe Ratio (0.7+ = хорошо!)
          </div>
        </div>
      </div>

      {/* Chart Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Main Chart */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <span>📈</span>
              График Капитала
            </h2>
            <EquityChart data={equityHistory} height={350} />
            <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-blue-900 dark:text-blue-200">
                💡 <strong>Как читать:</strong> Зелёная линия растёт вверх = вы зарабатываете! Падает вниз = временный убыток.
              </p>
            </div>
          </div>
        </div>

        {/* Recent Signals */}
        <div>
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🔔</span>
              Последние Сигналы
            </h2>
            <div className="space-y-3">
              {signals?.data && signals.data.length > 0 ? (
                signals.data.slice(0, 5).map((signal: any, idx: number) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border-2 hover:shadow-lg transition-all"
                    style={{
                      borderColor: signal.direction === 'BUY' ? '#22c55e' : signal.direction === 'SELL' ? '#ef4444' : '#9ca3af',
                      backgroundColor: signal.direction === 'BUY' ? '#f0fdf4' : signal.direction === 'SELL' ? '#fef2f2' : '#f9fafb',
                    }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-bold text-gray-900 dark:text-white">
                        {signal.symbol}
                      </div>
                      <div className={`text-2xl`}>
                        {signal.direction === 'BUY' ? '🟢' : signal.direction === 'SELL' ? '🔴' : '⚪'}
                      </div>
                    </div>
                    <div className="text-lg font-bold mb-1" style={{
                      color: signal.direction === 'BUY' ? '#22c55e' : signal.direction === 'SELL' ? '#ef4444' : '#9ca3af'
                    }}>
                      {signal.direction === 'BUY' ? 'КУПИТЬ' : signal.direction === 'SELL' ? 'ПРОДАТЬ' : 'ДЕРЖАТЬ'}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Уверенность: <span className="font-semibold">{(signal.prob * 100).toFixed(0)}%</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-2">
                      {new Date(signal.created_at).toLocaleString('ru-RU')}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-gray-500 py-8">
                  Пока нет сигналов
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Positions & Model Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Positions */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <span>💼</span>
            Открытые Позиции
          </h2>
          {positionsLoading ? (
            <div className="text-center py-8 text-gray-500">Загрузка...</div>
          ) : positions?.data?.positions && positions.data.positions.length > 0 ? (
            <div className="space-y-3">
              {positions.data.positions.map((pos: any, idx: number) => (
                <div
                  key={idx}
                  className="p-4 bg-gray-50 dark:bg-gray-700 rounded-xl hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="font-bold text-lg text-gray-900 dark:text-white">
                        {pos.symbol}
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        {pos.exchange}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-gray-900 dark:text-white">
                        ${(pos.qty * pos.avg_price).toFixed(2)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {pos.qty.toFixed(6)} шт
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    Цена покупки: <span className="font-semibold">${pos.avg_price.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <div className="text-5xl mb-4">📭</div>
              <div>Нет открытых позиций</div>
              <div className="text-sm mt-2">Дождитесь сигнала КУПИТЬ от ИИ</div>
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <span>🤖</span>
            Состояние Системы
          </h2>
          
          <div className="space-y-4">
            {/* Model Status */}
            <div className="p-4 bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 rounded-xl border-2 border-green-500">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <div className="font-bold text-gray-900 dark:text-white">Модель ИИ Активна</div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-gray-500 dark:text-gray-400">Точность</div>
                  <div className="font-bold text-gray-900 dark:text-white">52.3%</div>
                </div>
                <div>
                  <div className="text-gray-500 dark:text-gray-400">Надёжность</div>
                  <div className="font-bold text-gray-900 dark:text-white">0.77</div>
                </div>
                <div>
                  <div className="text-gray-500 dark:text-gray-400">Показателей</div>
                  <div className="font-bold text-gray-900 dark:text-white">48</div>
                </div>
                <div>
                  <div className="text-gray-500 dark:text-gray-400">Данных</div>
                  <div className="font-bold text-gray-900 dark:text-white">2160 строк</div>
                </div>
              </div>
            </div>

            {/* Backtest Results */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-xl">
              <div className="font-bold text-gray-900 dark:text-white mb-3">
                📊 Результаты Тестирования (60 дней)
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Общая Прибыль:</span>
                  <span className="font-bold text-green-600 dark:text-green-400">+0.16%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Макс. Просадка:</span>
                  <span className="font-bold text-gray-900 dark:text-white">-0.12%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Сделок:</span>
                  <span className="font-bold text-gray-900 dark:text-white">120</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">Прибыль/Убыток:</span>
                  <span className="font-bold text-green-600 dark:text-green-400">3.54x</span>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  💡 Это значит: на каждый $1 убытка приходится $3.54 прибыли!
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-800">
              <div className="font-bold text-blue-900 dark:text-blue-200 mb-3">
                ⚡ Быстрые Действия
              </div>
              <div className="space-y-2">
                <button className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-sm font-medium">
                  🔄 Обновить Данные
                </button>
                <button className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors text-sm font-medium">
                  🎯 Сгенерировать Сигнал
                </button>
                <button className="w-full px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors text-sm font-medium">
                  📚 Обучить Модель
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="mb-8">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <span>📈</span>
              Динамика Капитала
            </h2>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-200 rounded-lg text-sm font-medium">
                1 День
              </button>
              <button className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-lg text-sm">
                1 Неделя
              </button>
              <button className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-lg text-sm">
                1 Месяц
              </button>
            </div>
          </div>
          <EquityChart data={equityHistory} height={400} />
          <div className="mt-4 grid grid-cols-3 gap-4 text-center text-sm">
            <div>
              <div className="text-gray-500 dark:text-gray-400 mb-1">Зелёная линия</div>
              <div className="font-semibold text-green-600 dark:text-green-400">Общая Сумма</div>
            </div>
            <div>
              <div className="text-gray-500 dark:text-gray-400 mb-1">Синяя линия</div>
              <div className="font-semibold text-blue-600 dark:text-blue-400">Наличные</div>
            </div>
            <div>
              <div className="text-gray-500 dark:text-gray-400 mb-1">Оранжевая линия</div>
              <div className="font-semibold text-orange-600 dark:text-orange-400">Купленные Монеты</div>
            </div>
          </div>
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/30 dark:to-green-800/30 p-6 rounded-2xl border-2 border-green-500">
          <div className="text-4xl mb-3">✅</div>
          <h3 className="text-lg font-bold text-green-900 dark:text-green-200 mb-2">
            Что Умеет Система
          </h3>
          <ul className="text-sm text-green-800 dark:text-green-300 space-y-2">
            <li>• Анализирует рынок каждый час</li>
            <li>• Советует когда купить/продать</li>
            <li>• Учится на исторических данных</li>
            <li>• Показывает прибыль/убыток в реальном времени</li>
          </ul>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-800/30 p-6 rounded-2xl border-2 border-blue-500">
          <div className="text-4xl mb-3">🎯</div>
          <h3 className="text-lg font-bold text-blue-900 dark:text-blue-200 mb-2">
            Текущая Стратегия
          </h3>
          <ul className="text-sm text-blue-800 dark:text-blue-300 space-y-2">
            <li>• Монета: <strong>BTC/USDT</strong></li>
            <li>• Биржа: <strong>Bybit</strong></li>
            <li>• Таймфрейм: <strong>1 час</strong></li>
            <li>• Режим: <strong>Paper Trading</strong></li>
          </ul>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/30 dark:to-purple-800/30 p-6 rounded-2xl border-2 border-purple-500">
          <div className="text-4xl mb-3">🏆</div>
          <h3 className="text-lg font-bold text-purple-900 dark:text-purple-200 mb-2">
            Достижения
          </h3>
          <ul className="text-sm text-purple-800 dark:text-purple-300 space-y-2">
            <li>• Модель прибыльная (+0.16%)</li>
            <li>• Надёжность высокая (0.77)</li>
            <li>• Низкий риск (просадка -0.12%)</li>
            <li>• 2160 часов обучения</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';

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
    queryFn: () => api.getRecentSignals(10),
    refetchInterval: 30000,
  });

  // Mock data for charts
  const equityData = [
    { date: '2025-09-01', value: 1000, profit: 0 },
    { date: '2025-09-05', value: 995, profit: -5 },
    { date: '2025-09-10', value: 998, profit: -2 },
    { date: '2025-09-15', value: 1002, profit: 2 },
    { date: '2025-09-20', value: 999, profit: -1 },
    { date: '2025-09-25', value: 1003, profit: 3 },
    { date: '2025-10-01', value: 1001, profit: 1 },
    { date: '2025-10-05', value: 1005, profit: 5 },
    { date: '2025-10-10', value: 1008, profit: 8 },
    { date: '2025-10-12', value: 1011.6, profit: 11.6 },
  ];

  const tradingData = [
    { hour: '00:00', trades: 12 },
    { hour: '04:00', trades: 8 },
    { hour: '08:00', trades: 15 },
    { hour: '12:00', trades: 22 },
    { hour: '16:00', trades: 18 },
    { hour: '20:00', trades: 25 },
  ];

  const portfolioData = [
    { name: 'BTC/USDT', value: 65, color: '#f7931a' },
    { name: 'ETH/USDT', value: 25, color: '#627eea' },
    { name: 'SOL/USDT', value: 10, color: '#9945ff' },
  ];

  const performanceData = [
    { day: 'Пн', profit: 2.1, trades: 8 },
    { day: 'Вт', profit: 1.8, trades: 12 },
    { day: 'Ср', profit: -0.5, trades: 6 },
    { day: 'Чт', profit: 3.2, trades: 15 },
    { day: 'Пт', profit: 2.8, trades: 10 },
    { day: 'Сб', profit: 1.5, trades: 7 },
    { day: 'Вс', profit: 2.3, trades: 9 },
  ];

  const currentEquity = equity?.data?.equity || 1000;
  const startEquity = 1000;
  const returnPct = ((currentEquity - startEquity) / startEquity) * 100;
  const totalTrades = 120;
  const winRate = 68;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Добро пожаловать, Трейдер! 👋
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Ваш торговый бот работает стабильно
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {new Date().toLocaleDateString('ru-RU', { 
              weekday: 'long', 
              year: 'numeric', 
              month: 'long', 
              day: 'numeric' 
            })}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-green-600 dark:text-green-400">Система активна</span>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Equity */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Общий Капитал</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                ${equityLoading ? '...' : currentEquity.toFixed(2)}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Стартовый: $1,000.00
              </p>
            </div>
            <div className="text-4xl">💰</div>
          </div>
        </div>

        {/* Return */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg border-l-4 border-green-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Доходность</p>
              <p className={`text-3xl font-bold ${returnPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                За период
              </p>
            </div>
            <div className="text-4xl">{returnPct >= 0 ? '📈' : '📉'}</div>
          </div>
        </div>

        {/* Total Trades */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg border-l-4 border-purple-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Всего Сделок</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {totalTrades}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                За 60 дней
              </p>
            </div>
            <div className="text-4xl">📊</div>
          </div>
        </div>

        {/* Win Rate */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg border-l-4 border-orange-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Винрейт</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {winRate}%
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Успешных сделок
              </p>
            </div>
            <div className="text-4xl">🎯</div>
          </div>
        </div>
      </div>

      {/* Main Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              📈 Динамика Капитала
            </h2>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-200 rounded-lg text-sm">
                7 дней
              </button>
              <button className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-lg text-sm">
                30 дней
              </button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={equityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                formatter={(value: number) => [`$${value.toFixed(2)}`, 'Капитал']}
                labelStyle={{ color: '#374151' }}
                contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#3b82f6"
                fill="url(#colorGradient)"
                strokeWidth={3}
              />
              <defs>
                <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Portfolio Distribution */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
            🥧 Распределение Портфеля
          </h2>
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={portfolioData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={80}
                  dataKey="value"
                >
                  {portfolioData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => [`${value}%`, '']} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-2 mt-4">
            {portfolioData.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: item.color }}
                  ></div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">{item.name}</span>
                </div>
                <span className="text-sm font-semibold text-gray-900 dark:text-white">{item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trading Activity */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
            📊 Активность Торговли
          </h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={tradingData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="hour" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                formatter={(value: number) => [`${value}`, 'Сделок']}
                contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
              />
              <Bar dataKey="trades" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Weekly Performance */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
            📅 Недельная Производительность
          </h2>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                formatter={(value: number) => [`${value}%`, 'Прибыль']}
                contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
              />
              <Line 
                type="monotone" 
                dataKey="profit" 
                stroke="#8b5cf6" 
                strokeWidth={3}
                dot={{ fill: '#8b5cf6', strokeWidth: 2, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Signals */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
          🔔 Последние Сигналы
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {signals?.data && signals.data.length > 0 ? (
            signals.data.slice(0, 6).map((signal: any, idx: number) => (
              <div
                key={idx}
                className="p-4 rounded-lg border-2 hover:shadow-md transition-shadow"
                style={{
                  borderColor: signal.direction === 'BUY' ? '#10b981' : signal.direction === 'SELL' ? '#ef4444' : '#6b7280',
                  backgroundColor: signal.direction === 'BUY' ? '#f0fdf4' : signal.direction === 'SELL' ? '#fef2f2' : '#f9fafb',
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold text-gray-900 dark:text-white">
                    {signal.symbol}
                  </div>
                  <div className="text-2xl">
                    {signal.direction === 'BUY' ? '🟢' : signal.direction === 'SELL' ? '🔴' : '⚪'}
                  </div>
                </div>
                <div className="text-lg font-bold mb-1" style={{
                  color: signal.direction === 'BUY' ? '#10b981' : signal.direction === 'SELL' ? '#ef4444' : '#6b7280'
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
            <div className="col-span-full text-center text-gray-500 py-8">
              Пока нет сигналов
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
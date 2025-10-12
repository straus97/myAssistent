'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import SignalsTable from '@/components/SignalsTable';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar } from 'recharts';

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

  // Extended equity history for detailed analysis
  const equityHistory = [
    { timestamp: '2025-09-01', equity: 1000, cash: 1000, positions_value: 0 },
    { timestamp: '2025-09-05', equity: 995, cash: 800, positions_value: 195 },
    { timestamp: '2025-09-10', equity: 998, cash: 850, positions_value: 148 },
    { timestamp: '2025-09-15', equity: 1002, cash: 900, positions_value: 102 },
    { timestamp: '2025-09-20', equity: 999, cash: 950, positions_value: 49 },
    { timestamp: '2025-09-25', equity: 1003, cash: 800, positions_value: 203 },
    { timestamp: '2025-10-01', equity: 1001, cash: 850, positions_value: 151 },
    { timestamp: '2025-10-05', equity: 1005, cash: 900, positions_value: 105 },
    { timestamp: '2025-10-10', equity: 1008, cash: 950, positions_value: 58 },
    { timestamp: '2025-10-12', equity: 1011.6, cash: 900, positions_value: 111.6 },
  ];

  const tradingStats = [
    { metric: 'Всего сделок', value: '120', change: '+12', changeType: 'positive' },
    { metric: 'Прибыльных', value: '82', change: '+8', changeType: 'positive' },
    { metric: 'Убыточных', value: '38', change: '+4', changeType: 'negative' },
    { metric: 'Средняя прибыль', value: '$2.3', change: '+$0.4', changeType: 'positive' },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            📊 Аналитический Дашборд
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Детальная статистика и производительность
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Обновлено: {new Date().toLocaleTimeString('ru-RU')}
          </span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {tradingStats.map((stat, idx) => (
          <div key={idx} className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg border-l-4 border-blue-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{stat.metric}</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</p>
                <p className={`text-sm ${stat.changeType === 'positive' ? 'text-green-600' : 'text-red-600'}`}>
                  {stat.change} за неделю
                </p>
              </div>
              <div className="text-3xl">
                {idx === 0 && '📊'}
                {idx === 1 && '✅'}
                {idx === 2 && '❌'}
                {idx === 3 && '💰'}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Equity Chart */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              📈 Динамика Капитала
            </h2>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-200 rounded-lg text-sm">
                30 дней
              </button>
              <button className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-lg text-sm">
                90 дней
              </button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={equityHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                formatter={(value: number) => [`$${value.toFixed(2)}`, 'Капитал']}
                labelStyle={{ color: '#374151' }}
                contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
              />
              <Area
                type="monotone"
                dataKey="equity"
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

        {/* Cash vs Positions */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
            💰 Наличные vs Позиции
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={equityHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip 
                formatter={(value: number) => [`$${value.toFixed(2)}`, '']}
                contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
              />
              <Line 
                type="monotone" 
                dataKey="cash" 
                stroke="#10b981" 
                strokeWidth={3}
                dot={{ fill: '#10b981', strokeWidth: 2, r: 4 }}
              />
              <Line 
                type="monotone" 
                dataKey="positions_value" 
                stroke="#f59e0b" 
                strokeWidth={3}
                dot={{ fill: '#f59e0b', strokeWidth: 2, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-4 flex justify-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span className="text-gray-600 dark:text-gray-400">Наличные</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
              <span className="text-gray-600 dark:text-gray-400">В Позициях</span>
            </div>
          </div>
        </div>
      </div>

      {/* Signals Section */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
          🔔 Все Сигналы
        </h2>
        <SignalsTable signals={signals?.data || []} loading={signalsLoading} />
      </div>
    </div>
  );
}

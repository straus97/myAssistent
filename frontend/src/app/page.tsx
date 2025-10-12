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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card shadow-sm border-b border-border">
        <div className="px-6 py-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                Добро пожаловать, Трейдер! 👋
              </h1>
              <p className="text-muted-foreground mt-1">
                Ваш торговый бот работает стабильно и приносит прибыль
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm text-muted-foreground">
                  {new Date().toLocaleDateString('ru-RU', { 
                    weekday: 'long', 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                  })}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm text-green-600 dark:text-green-400 font-medium">Система активна</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6 space-y-8">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Total Equity */}
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border hover:shadow-xl transition-all duration-300 animate-slide-up">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Общий Капитал</p>
                <p className="text-3xl font-bold text-foreground">
                  ${equityLoading ? '...' : currentEquity.toFixed(2)}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Стартовый: $1,000.00
                </p>
              </div>
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center">
                <span className="text-xl">💰</span>
              </div>
            </div>
          </div>

          {/* Return */}
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border hover:shadow-xl transition-all duration-300 animate-slide-up">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Доходность</p>
                <p className={`text-3xl font-bold ${returnPct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  За период
                </p>
              </div>
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-xl flex items-center justify-center">
                <span className="text-xl">{returnPct >= 0 ? '📈' : '📉'}</span>
              </div>
            </div>
          </div>

          {/* Total Trades */}
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border hover:shadow-xl transition-all duration-300 animate-slide-up">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Всего Сделок</p>
                <p className="text-3xl font-bold text-foreground">
                  {totalTrades}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  За 60 дней
                </p>
              </div>
              <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-xl flex items-center justify-center">
                <span className="text-xl">📊</span>
              </div>
            </div>
          </div>

          {/* Win Rate */}
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border hover:shadow-xl transition-all duration-300 animate-slide-up">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Винрейт</p>
                <p className="text-3xl font-bold text-foreground">
                  {winRate}%
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Успешных сделок
                </p>
              </div>
              <div className="w-12 h-12 bg-orange-100 dark:bg-orange-900/20 rounded-xl flex items-center justify-center">
                <span className="text-xl">🎯</span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Charts Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Equity Chart */}
          <div className="xl:col-span-2 bg-card p-6 rounded-2xl shadow-lg border border-border animate-slide-up">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
              <h2 className="text-xl font-bold text-foreground mb-2 sm:mb-0">
                📈 Динамика Капитала
              </h2>
              <div className="flex gap-2">
                <button className="px-4 py-2 bg-primary/10 text-primary rounded-lg text-sm font-medium hover:bg-primary/20 transition-colors">
                  7 дней
                </button>
                <button className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm font-medium hover:bg-secondary/80 transition-colors">
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
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e7eb', 
                    borderRadius: '12px',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
                  }}
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
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border animate-slide-up">
            <h2 className="text-xl font-bold text-foreground mb-6">
              🥧 Распределение Портфеля
            </h2>
            <div className="flex items-center justify-center mb-6">
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
                  <Tooltip 
                    formatter={(value: number) => [`${value}%`, '']} 
                    contentStyle={{ 
                      backgroundColor: 'white', 
                      border: '1px solid #e5e7eb', 
                      borderRadius: '12px',
                      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
                    }} 
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-3">
              {portfolioData.map((item, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-4 h-4 rounded-full" 
                      style={{ backgroundColor: item.color }}
                    ></div>
                    <span className="text-sm text-muted-foreground font-medium">{item.name}</span>
                  </div>
                  <span className="text-sm font-bold text-foreground">{item.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Trading Activity */}
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border animate-slide-up">
            <h2 className="text-xl font-bold text-foreground mb-6">
              📊 Активность Торговли
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={tradingData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="hour" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip 
                  formatter={(value: number) => [`${value}`, 'Сделок']}
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e7eb', 
                    borderRadius: '12px',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
                  }}
                />
                <Bar dataKey="trades" fill="#10b981" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Weekly Performance */}
          <div className="bg-card p-6 rounded-2xl shadow-lg border border-border animate-slide-up">
            <h2 className="text-xl font-bold text-foreground mb-6">
              📅 Недельная Производительность
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip 
                  formatter={(value: number) => [`${value}%`, 'Прибыль']}
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e7eb', 
                    borderRadius: '12px',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
                  }}
                />
                <Line 
                  type="monotone" 
                  dataKey="profit" 
                  stroke="#8b5cf6" 
                  strokeWidth={3}
                  dot={{ fill: '#8b5cf6', strokeWidth: 2, r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Signals */}
        <div className="bg-card p-6 rounded-2xl shadow-lg border border-border animate-slide-up">
          <h2 className="text-xl font-bold text-foreground mb-6">
            🔔 Последние Сигналы
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {signals?.data && signals.data.length > 0 ? (
              signals.data.slice(0, 6).map((signal: any, idx: number) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl border-2 hover:shadow-lg transition-all duration-300 cursor-pointer transform hover:scale-105"
                  style={{
                    borderColor: signal.direction === 'BUY' ? '#10b981' : signal.direction === 'SELL' ? '#ef4444' : '#6b7280',
                    backgroundColor: signal.direction === 'BUY' ? '#f0fdf4' : signal.direction === 'SELL' ? '#fef2f2' : '#f9fafb',
                  }}
                >
                  <div className="flex flex-col items-center text-center">
                    <div className="text-3xl mb-2">
                      {signal.direction === 'BUY' ? '🟢' : signal.direction === 'SELL' ? '🔴' : '⚪'}
                    </div>
                    <div className="font-bold text-foreground mb-1">
                      {signal.symbol}
                    </div>
                    <div className="text-lg font-bold mb-2" style={{
                      color: signal.direction === 'BUY' ? '#10b981' : signal.direction === 'SELL' ? '#ef4444' : '#6b7280'
                    }}>
                      {signal.direction === 'BUY' ? 'КУПИТЬ' : signal.direction === 'SELL' ? 'ПРОДАТЬ' : 'ДЕРЖАТЬ'}
                    </div>
                    <div className="text-sm text-muted-foreground mb-1">
                      Уверенность: <span className="font-semibold">{(signal.prob * 100).toFixed(0)}%</span>
                    </div>
                    <div className="text-xs text-muted-foreground/70">
                      {new Date(signal.created_at).toLocaleString('ru-RU', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-full text-center text-muted-foreground py-12">
                <div className="text-4xl mb-4">🔔</div>
                <div className="text-lg font-medium">Пока нет сигналов</div>
                <div className="text-sm mt-2">Дождитесь генерации новых сигналов</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
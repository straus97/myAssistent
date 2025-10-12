'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import EquityChart from '@/components/EquityChart';
import MetricsCard from '@/components/MetricsCard';
import SignalsTable from '@/components/SignalsTable';

export default function Dashboard() {
  // Real-time data fetching
  const { data: equity, isLoading: equityLoading } = useQuery({
    queryKey: ['equity'],
    queryFn: () => api.getEquity(),
    refetchInterval: 10000, // 10 seconds
  });

  const { data: positions, isLoading: positionsLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.getPositions(),
    refetchInterval: 10000,
  });

  const { data: signals, isLoading: signalsLoading } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getRecentSignals(20),
    refetchInterval: 30000, // 30 seconds
  });

  const { data: modelHealth, isLoading: healthLoading } = useQuery({
    queryKey: ['modelHealth'],
    queryFn: () => api.getModelHealth(),
    refetchInterval: 60000, // 1 minute
  });

  // Mock equity history для графика (в production будет из API)
  const equityHistory = [
    { timestamp: '2025-10-01', equity: 1000, cash: 1000, positions_value: 0 },
    { timestamp: '2025-10-05', equity: 995, cash: 800, positions_value: 195 },
    { timestamp: '2025-10-10', equity: 1001.6, cash: 900, positions_value: 101.6 },
  ];

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
            MyAssistent Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Autonomous Trading Bot • ML-powered • Version 1.0
          </p>
        </header>

        {/* Key Metrics */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Portfolio Overview
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MetricsCard
              title="Total Equity"
              value={equityLoading ? '...' : `$${equity?.data?.equity?.toFixed(2) || '0.00'}`}
              trend="up"
            />
            <MetricsCard
              title="Cash"
              value={equityLoading ? '...' : `$${equity?.data?.cash?.toFixed(2) || '0.00'}`}
              trend="neutral"
            />
            <MetricsCard
              title="Positions"
              value={positionsLoading ? '...' : positions?.data?.positions?.length || 0}
              subtitle={`Value: $${equity?.data?.positions_value?.toFixed(2) || '0.00'}`}
              trend="neutral"
            />
            <MetricsCard
              title="Return"
              value="+0.16%"
              subtitle="Sharpe: 0.77"
              trend="up"
            />
          </div>
        </section>

        {/* Equity Chart */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Equity Curve
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <EquityChart data={equityHistory} height={300} />
          </div>
        </section>

        {/* Positions Table */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Open Positions
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
            {positionsLoading ? (
              <div className="p-6 text-center text-gray-500">Loading...</div>
            ) : positions?.data?.positions && positions.data.positions.length > 0 ? (
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Exchange
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Symbol
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Quantity
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Avg Price
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Current Value
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {positions.data.positions.map((pos: any, idx: number) => (
                    <tr key={idx}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {pos.exchange}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                        {pos.symbol}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {pos.qty.toFixed(6)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        ${pos.avg_price.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        ${(pos.qty * pos.avg_price).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-6 text-center text-gray-500 dark:text-gray-400">
                Нет открытых позиций
              </div>
            )}
          </div>
        </section>

        {/* Recent Signals */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Недавние Сигналы
          </h2>
          <SignalsTable 
            signals={signals?.data || []} 
            loading={signalsLoading} 
          />
        </section>

        {/* Model Health */}
        <section>
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Состояние Моделей
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {healthLoading ? (
              <div className="col-span-full p-6 text-center text-gray-500">Loading...</div>
            ) : modelHealth?.data && modelHealth.data.length > 0 ? (
              modelHealth.data.map((model: any, idx: number) => (
                <div key={idx} className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {model.symbol}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {model.timeframe} • Horizon: {model.horizon_steps}
                      </p>
                    </div>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        model.fresh
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                      }`}
                    >
                      {model.fresh ? 'Fresh' : 'Stale'}
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">ROC AUC:</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {model.auc?.toFixed(3) || 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Age:</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {model.age_days?.toFixed(1) || '0'} days
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Features:</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {model.n_features || 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-full p-6 text-center text-gray-500 dark:text-gray-400">
                Модели не обучены
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}


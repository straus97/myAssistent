'use client';

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export default function Dashboard() {
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
    queryFn: () => api.getRecentSignals(10),
    refetchInterval: 30000, // 30 seconds
  });

  const { data: modelHealth, isLoading: healthLoading } = useQuery({
    queryKey: ['modelHealth'],
    queryFn: () => api.getModelHealth(),
    refetchInterval: 60000, // 1 minute
  });

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
            MyAssistent Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Autonomous trading bot with ML • Version 0.9
          </p>
        </header>

        {/* Equity Section */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Portfolio Equity
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
              <p className="text-sm text-gray-500 dark:text-gray-400">Cash</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {equityLoading ? '...' : `${equity?.data?.cash.toFixed(2) || 0} ₽`}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
              <p className="text-sm text-gray-500 dark:text-gray-400">Positions Value</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {equityLoading ? '...' : `${equity?.data?.positions_value.toFixed(2) || 0} ₽`}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Equity</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                {equityLoading ? '...' : `${equity?.data?.equity.toFixed(2) || 0} ₽`}
              </p>
            </div>
          </div>
        </section>

        {/* Positions Section */}
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
                      Symbol
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Exchange
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Qty
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                      Avg Price
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {positions.data.positions.map((pos: any, idx: number) => (
                    <tr key={idx}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                        {pos.symbol}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {pos.exchange}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {pos.qty.toFixed(4)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        ${pos.avg_price.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-6 text-center text-gray-500 dark:text-gray-400">
                No open positions
              </div>
            )}
          </div>
        </section>

        {/* Recent Signals */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Recent Signals
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
            {signalsLoading ? (
              <div className="p-6 text-center text-gray-500">Loading...</div>
            ) : signals?.data && signals.data.length > 0 ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {signals.data.slice(0, 5).map((signal: any, idx: number) => (
                  <div key={idx} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {signal.symbol} ({signal.timeframe})
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {new Date(signal.created_at).toLocaleString()}
                        </p>
                      </div>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-medium ${
                          signal.direction === 'BUY'
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : signal.direction === 'SELL'
                            ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {signal.direction}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-gray-500 dark:text-gray-400">
                No recent signals
              </div>
            )}
          </div>
        </section>

        {/* Model Health */}
        <section>
          <h2 className="text-2xl font-semibold mb-4 text-gray-800 dark:text-gray-200">
            Model Health
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
            {healthLoading ? (
              <div className="p-6 text-center text-gray-500">Loading...</div>
            ) : modelHealth?.data && modelHealth.data.length > 0 ? (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {modelHealth.data.slice(0, 5).map((model: any, idx: number) => (
                  <div key={idx} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {model.symbol} ({model.timeframe})
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Age: {model.age_days.toFixed(1)} days • AUC: {model.auc?.toFixed(3) || 'N/A'}
                        </p>
                      </div>
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-medium ${
                          model.fresh
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                        }`}
                      >
                        {model.fresh ? 'Fresh' : 'Stale'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-gray-500 dark:text-gray-400">
                No models trained
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}


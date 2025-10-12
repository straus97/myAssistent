'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface EquityPoint {
  timestamp: string;
  equity: number;
  cash: number;
  positions_value: number;
}

interface EquityChartProps {
  data: EquityPoint[];
  height?: number;
}

export default function EquityChart({ data, height = 400 }: EquityChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height: `${height}px` }}>
        <p className="text-gray-500 dark:text-gray-400">No data available</p>
      </div>
    );
  }

  // Format data для recharts
  const chartData = data.map(d => ({
    date: new Date(d.timestamp).toLocaleDateString('ru-RU'),
    equity: d.equity,
    cash: d.cash,
    positions: d.positions_value,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
        <XAxis 
          dataKey="date" 
          className="text-xs text-gray-600 dark:text-gray-400"
        />
        <YAxis 
          className="text-xs text-gray-600 dark:text-gray-400"
          tickFormatter={(value) => `$${value}`}
        />
        <Tooltip 
          contentStyle={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '1px solid #e5e7eb',
            borderRadius: '0.5rem',
          }}
          formatter={(value: number) => [`$${value.toFixed(2)}`, '']}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="equity"
          stroke="#22c55e"
          strokeWidth={3}
          dot={false}
          name="Total Equity"
        />
        <Line
          type="monotone"
          dataKey="cash"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          name="Cash"
        />
        <Line
          type="monotone"
          dataKey="positions"
          stroke="#fb923c"
          strokeWidth={2}
          dot={false}
          name="Positions Value"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}


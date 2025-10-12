'use client';

import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface BacktestDataPoint {
  timestamp: string;
  equity: number;
  drawdown?: number;
}

interface BacktestChartProps {
  data: BacktestDataPoint[];
  initialCapital?: number;
  height?: number;
}

export default function BacktestChart({ 
  data, 
  initialCapital = 1000, 
  height = 400 
}: BacktestChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height: `${height}px` }}>
        <p className="text-gray-500 dark:text-gray-400">No backtest data</p>
      </div>
    );
  }

  // Format data для recharts
  const chartData = data.map(d => ({
    date: new Date(d.timestamp).toLocaleDateString('ru-RU'),
    equity: d.equity,
    drawdown: d.drawdown || 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="date" 
          className="text-xs"
        />
        <YAxis 
          yAxisId="left"
          orientation="left"
          label={{ value: 'Equity ($)', angle: -90, position: 'insideLeft' }}
          tickFormatter={(value) => `$${value}`}
        />
        <YAxis 
          yAxisId="right"
          orientation="right"
          label={{ value: 'Drawdown (%)', angle: 90, position: 'insideRight' }}
          tickFormatter={(value) => `${value}%`}
        />
        <Tooltip 
          formatter={(value: number, name: string) => {
            if (name === 'Equity') return [`$${value.toFixed(2)}`, 'Equity'];
            return [`${value.toFixed(2)}%`, 'Drawdown'];
          }}
        />
        <Legend />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="equity"
          stroke="#22c55e"
          strokeWidth={3}
          dot={false}
          name="Equity"
        />
        <Area
          yAxisId="right"
          type="monotone"
          dataKey="drawdown"
          fill="#ef4444"
          stroke="#ef4444"
          fillOpacity={0.3}
          strokeWidth={2}
          name="Drawdown"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}


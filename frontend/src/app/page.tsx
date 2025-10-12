'use client';

import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-6xl font-bold text-gray-900 dark:text-white mb-4">
            MyAssistent
          </h1>
          <p className="text-2xl text-gray-600 dark:text-gray-300 mb-2">
            Autonomous Trading Bot
          </p>
          <p className="text-lg text-gray-500 dark:text-gray-400">
            ML-powered • Profitable • Version 1.0
          </p>
          
          {/* Stats Badge */}
          <div className="mt-8 inline-flex items-center gap-6 bg-white dark:bg-gray-800 px-8 py-4 rounded-full shadow-lg">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">+0.16%</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Return</p>
            </div>
            <div className="h-8 w-px bg-gray-300 dark:bg-gray-600"></div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">0.77</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Sharpe Ratio</p>
            </div>
            <div className="h-8 w-px bg-gray-300 dark:bg-gray-600"></div>
            <div className="text-center">
              <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">48</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Features</p>
            </div>
          </div>
        </div>

        {/* Navigation Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Dashboard */}
          <Link href="/dashboard">
            <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl hover:shadow-2xl transition-shadow cursor-pointer border-2 border-transparent hover:border-blue-500">
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                Dashboard
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Equity curve, позиции, сигналы
              </p>
            </div>
          </Link>

          {/* Backtest */}
          <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl opacity-75">
            <div className="text-4xl mb-4">🧪</div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Backtest
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Результаты симуляции (скоро)
            </p>
          </div>

          {/* Models */}
          <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl opacity-75">
            <div className="text-4xl mb-4">🤖</div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Models
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              ML модели и метрики (скоро)
            </p>
          </div>

          {/* Settings */}
          <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl opacity-75">
            <div className="text-4xl mb-4">⚙️</div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Settings
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Риск-политика, конфигурация (скоро)
            </p>
          </div>

          {/* News */}
          <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl opacity-75">
            <div className="text-4xl mb-4">📰</div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              News
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Новости с sentiment (скоро)
            </p>
          </div>

          {/* API Docs */}
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">
            <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl hover:shadow-2xl transition-shadow cursor-pointer border-2 border-transparent hover:border-green-500">
              <div className="text-4xl mb-4">📖</div>
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                API Docs
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Swagger UI (Backend API)
              </p>
            </div>
          </a>
        </div>

        {/* Footer Info */}
        <div className="mt-16 text-center">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              Quick Links
            </h3>
            <div className="flex flex-wrap justify-center gap-4">
              <a 
                href="http://localhost:8000" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                Backend API (:8000)
              </a>
              <span className="text-gray-300 dark:text-gray-600">•</span>
              <a 
                href="http://localhost:5000" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                MLflow (:5000)
              </a>
              <span className="text-gray-300 dark:text-gray-600">•</span>
              <a 
                href="http://localhost:9090" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                Prometheus (:9090)
              </a>
              <span className="text-gray-300 dark:text-gray-600">•</span>
              <a 
                href="http://localhost:3001" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                Grafana (:3001)
              </a>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

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
            Торговый Бот на Искусственном Интеллекте
          </p>
          <p className="text-lg text-gray-500 dark:text-gray-400">
            Прибыльная модель • Автоматическая торговля • Версия 1.0
          </p>
          
          {/* Stats Badge */}
          <div className="mt-8 inline-flex items-center gap-6 bg-white dark:bg-gray-800 px-8 py-4 rounded-full shadow-lg">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">+0.16%</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Доходность</p>
            </div>
            <div className="h-8 w-px bg-gray-300 dark:bg-gray-600"></div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">0.77</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Коэф. Шарпа</p>
            </div>
            <div className="h-8 w-px bg-gray-300 dark:bg-gray-600"></div>
            <div className="text-center">
              <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">48</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Показателей</p>
            </div>
          </div>
        </div>

        {/* Navigation Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Dashboard - ГЛАВНЫЙ */}
          <Link href="/dashboard">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-8 rounded-2xl shadow-xl hover:shadow-2xl transition-all cursor-pointer transform hover:scale-105">
              <div className="text-5xl mb-4">📊</div>
              <h3 className="text-2xl font-bold text-white mb-2">
                Дашборд
              </h3>
              <p className="text-blue-100">
                Портфель, графики, сигналы
              </p>
              <div className="mt-4 text-sm text-blue-200">
                👉 Начните отсюда!
              </div>
            </div>
          </Link>

          {/* Помощь */}
          <Link href="/help">
            <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl hover:shadow-2xl transition-shadow cursor-pointer border-2 border-transparent hover:border-green-500">
              <div className="text-4xl mb-4">❓</div>
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                Что это такое?
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Объяснение сервисов и как пользоваться
              </p>
            </div>
          </Link>

          {/* API для разработчиков */}
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">
            <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl hover:shadow-2xl transition-shadow cursor-pointer border-2 border-transparent hover:border-purple-500">
              <div className="text-4xl mb-4">⚙️</div>
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                API (для программистов)
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Техническая документация
              </p>
            </div>
          </a>
        </div>

        {/* Footer Info */}
        <div className="mt-16">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-8 shadow-lg">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 text-center">
              💡 Дополнительные сервисы (для продвинутых пользователей)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">🔬</span>
                  <a 
                    href="http://localhost:5000" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    MLflow (:5000)
                  </a>
                </div>
                <p className="text-gray-600 dark:text-gray-300 text-xs">
                  История обучения моделей, сравнение версий. Нужен только программистам.
                </p>
              </div>
              
              <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">📈</span>
                  <a 
                    href="http://localhost:3001" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Grafana (:3001)
                  </a>
                </div>
                <p className="text-gray-600 dark:text-gray-300 text-xs">
                  Технический мониторинг (скорость API, нагрузка). Нужен только для отладки.
                </p>
              </div>
            </div>
            
            <p className="text-center text-xs text-gray-500 dark:text-gray-400 mt-4">
              🎯 Для обычного использования достаточно только <strong>Дашборда</strong>!
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

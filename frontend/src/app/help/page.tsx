'use client';

import Link from 'next/link';

export default function HelpPage() {
  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8">
          <Link href="/" className="text-blue-600 dark:text-blue-400 hover:underline mb-4 inline-block">
            ← Назад на главную
          </Link>
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
            📚 Справка: Что Это Такое?
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Понятное объяснение всех сервисов MyAssistent
          </p>
        </header>

        {/* Основной интерфейс */}
        <section className="mb-12 bg-blue-50 dark:bg-blue-900/20 p-6 rounded-xl border-2 border-blue-500">
          <h2 className="text-2xl font-bold text-blue-900 dark:text-blue-300 mb-4 flex items-center gap-2">
            <span className="text-3xl">🎯</span>
            Дашборд (localhost:3000) — ВАШ ГЛАВНЫЙ ЭКРАН
          </h2>
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            <strong>Это единственный экран, который вам нужен!</strong> Здесь всё для работы:
          </p>
          <ul className="space-y-2 text-gray-700 dark:text-gray-300">
            <li className="flex items-start gap-2">
              <span className="text-green-600 dark:text-green-400">✅</span>
              <div>
                <strong>Портфель</strong> — сколько у вас денег (наличные + стоимость купленных монет)
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-600 dark:text-green-400">✅</span>
              <div>
                <strong>График прибыли</strong> — как растёт ваш капитал (зелёная линия вверх = прибыль!)
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-600 dark:text-green-400">✅</span>
              <div>
                <strong>Открытые позиции</strong> — какие монеты вы сейчас купили (BTC, ETH, и т.д.)
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-600 dark:text-green-400">✅</span>
              <div>
                <strong>Сигналы</strong> — что советует искусственный интеллект:
                <ul className="ml-4 mt-1 space-y-1 text-sm">
                  <li>🟢 <strong>BUY</strong> = Советует купить (цена может вырасти)</li>
                  <li>🔴 <strong>SELL</strong> = Советует продать (цена может упасть)</li>
                  <li>⚪ <strong>HOLD</strong> = Советует держать (ждать)</li>
                </ul>
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-600 dark:text-green-400">✅</span>
              <div>
                <strong>Состояние модели ИИ</strong> — насколько точно работает искусственный интеллект
              </div>
            </li>
          </ul>
          <div className="mt-4 p-4 bg-blue-100 dark:bg-blue-800/30 rounded-lg">
            <p className="text-sm text-blue-900 dark:text-blue-200">
              💡 <strong>Совет:</strong> Закладка только на Дашборд (localhost:3000/dashboard) — там всё что нужно!
            </p>
          </div>
        </section>

        {/* MLflow */}
        <section className="mb-8 bg-white dark:bg-gray-800 p-6 rounded-xl shadow">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <span className="text-3xl">🔬</span>
            MLflow (localhost:5000) — Для Программистов
          </h2>
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            <strong>Что это:</strong> Система для отслеживания экспериментов с искусственным интеллектом.
          </p>
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg mb-4">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              <strong>Что там происходит:</strong>
            </p>
            <ul className="mt-2 space-y-1 text-sm text-gray-600 dark:text-gray-400 ml-4">
              <li>• История обучения моделей (когда, с какими параметрами)</li>
              <li>• Сравнение разных версий моделей</li>
              <li>• Метрики точности (ROC AUC, Accuracy, и т.д.)</li>
              <li>• Сохранённые файлы моделей</li>
            </ul>
          </div>
          <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border-l-4 border-yellow-500">
            <p className="text-sm text-yellow-900 dark:text-yellow-200">
              ⚠️ <strong>Для обычных пользователей:</strong> Можно закрыть эту вкладку! Используется только при переобучении модели.
            </p>
          </div>
        </section>

        {/* Grafana */}
        <section className="mb-8 bg-white dark:bg-gray-800 p-6 rounded-xl shadow">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <span className="text-3xl">📊</span>
            Grafana (localhost:3001) — Технический Мониторинг
          </h2>
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            <strong>Что это:</strong> Система мониторинга технических показателей сервера.
          </p>
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg mb-4">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              <strong>Что там происходит:</strong>
            </p>
            <ul className="mt-2 space-y-1 text-sm text-gray-600 dark:text-gray-400 ml-4">
              <li>• Скорость работы API (время ответа в миллисекундах)</li>
              <li>• Нагрузка на сервер (CPU, память)</li>
              <li>• Количество запросов в секунду</li>
              <li>• Графики производительности системы</li>
            </ul>
          </div>
          <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border-l-4 border-yellow-500">
            <p className="text-sm text-yellow-900 dark:text-yellow-200">
              ⚠️ <strong>Для обычных пользователей:</strong> Можно закрыть! Нужна только при проблемах с производительностью или для IT-администраторов.
            </p>
          </div>
          <div className="mt-4 p-4 bg-gray-100 dark:bg-gray-700 rounded-lg">
            <p className="text-xs text-gray-600 dark:text-gray-400">
              🔑 Логин: <code className="bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded">admin</code><br/>
              🔑 Пароль: <code className="bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded">admin</code>
            </p>
          </div>
        </section>

        {/* Summary */}
        <section className="bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 p-8 rounded-xl border-2 border-green-500">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 text-center">
            🎯 Что Мне Использовать?
          </h2>
          
          <div className="space-y-4">
            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg">
              <h3 className="font-bold text-green-600 dark:text-green-400 mb-2">
                ✅ ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ:
              </h3>
              <p className="text-gray-700 dark:text-gray-300">
                Используйте только <strong>Дашборд</strong> (localhost:3000/dashboard)<br/>
                Там есть ВСЁ: портфель, графики, сигналы, позиции.
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg">
              <h3 className="font-bold text-blue-600 dark:text-blue-400 mb-2">
                🔧 ДЛЯ ПРОГРАММИСТОВ:
              </h3>
              <ul className="text-gray-700 dark:text-gray-300 space-y-1 text-sm">
                <li>• <strong>API Docs</strong> (localhost:8000/docs) — техническая документация</li>
                <li>• <strong>MLflow</strong> (localhost:5000) — история обучения моделей</li>
                <li>• <strong>Grafana</strong> (localhost:3001) — мониторинг производительности</li>
              </ul>
            </div>
          </div>

          <div className="mt-6 text-center">
            <Link 
              href="/dashboard" 
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg shadow-lg transition-colors"
            >
              👉 Перейти на Дашборд
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}


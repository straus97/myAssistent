'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const menuItems = [
  { href: '/', label: 'Главная', icon: '🏠' },
  { href: '/dashboard', label: 'Дашборд', icon: '📊' },
  { href: '/signals', label: 'Сигналы', icon: '🔔' },
  { href: '/portfolio', label: 'Портфель', icon: '💼' },
  { href: '/help', label: 'Помощь', icon: '❓' },
];

const externalLinks = [
  { href: 'http://localhost:8000/docs', label: 'API Docs', icon: '⚙️' },
  { href: 'http://localhost:5000', label: 'MLflow', icon: '🔬', badge: 'Для разработчиков' },
  { href: 'http://localhost:3001', label: 'Grafana', icon: '📈', badge: 'Для админов' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-gradient-to-b from-gray-900 to-gray-800 text-white h-screen fixed left-0 top-0 flex flex-col shadow-2xl">
      {/* Logo */}
      <div className="p-6 border-b border-gray-700">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
          MyAssistent
        </h1>
        <p className="text-xs text-gray-400 mt-1">Торговый Бот на ИИ</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-1">
          {menuItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link key={item.href} href={item.href}>
                <div
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all cursor-pointer ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-lg transform scale-105'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`}
                >
                  <span className="text-xl">{item.icon}</span>
                  <span className="font-medium">{item.label}</span>
                </div>
              </Link>
            );
          })}
        </div>

        {/* Separator */}
        <div className="my-6 border-t border-gray-700"></div>

        {/* External Links */}
        <div className="space-y-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider px-4 mb-2">
            Доп. сервисы
          </p>
          {externalLinks.map((item) => (
            <a
              key={item.href}
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              className="block"
            >
              <div className="flex items-center gap-3 px-4 py-2 rounded-lg text-gray-400 hover:bg-gray-700 hover:text-white transition-all cursor-pointer">
                <span className="text-lg">{item.icon}</span>
                <div className="flex-1">
                  <div className="text-sm">{item.label}</div>
                  {item.badge && (
                    <div className="text-xs text-gray-500">{item.badge}</div>
                  )}
                </div>
                <span className="text-xs">↗</span>
              </div>
            </a>
          ))}
        </div>
      </nav>

      {/* Status */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-gray-400">Система работает</span>
        </div>
        <div className="mt-2 text-xs text-gray-500">
          v1.0 • Прибыльная модель
        </div>
      </div>
    </aside>
  );
}


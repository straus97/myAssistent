'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import ThemeToggle from './ThemeToggle';

const menuItems = [
  { href: '/', label: 'Главная', icon: '🏠' },
  { href: '/dashboard', label: 'Дашборд', icon: '📊' },
  { href: '/signals', label: 'Сигналы', icon: '🔔' },
  { href: '/portfolio', label: 'Портфель', icon: '💼' },
  { href: '/help', label: 'Помощь', icon: '❓' },
];

const externalLinks = [
  { href: 'http://localhost:8000/docs', label: 'API Docs', icon: '⚙️', badge: 'Для разработчиков' },
  { href: 'http://localhost:5000', label: 'MLflow', icon: '🔬', badge: 'Для разработчиков' },
  { href: 'http://localhost:3001', label: 'Grafana', icon: '📈', badge: 'Для админов' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <>
      {/* Mobile Overlay */}
      <div className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40" />
      
      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-screen bg-card border-r border-border
        transition-all duration-300 ease-in-out z-50
        ${isCollapsed ? 'w-16' : 'w-64'}
        lg:translate-x-0
      `}>
        {/* Logo */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            {!isCollapsed && (
              <div>
                <h1 className="text-xl font-bold text-foreground">
                  MyAssistent
                </h1>
                <p className="text-xs text-muted-foreground">Торговый Бот на ИИ</p>
              </div>
            )}
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="p-2 rounded-lg hover:bg-accent transition-colors"
              >
                <svg className="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto">
          <div className="space-y-2">
            {menuItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link key={item.href} href={item.href}>
                  <div
                    className={`
                      flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 cursor-pointer group
                      ${isActive
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      }
                      ${isCollapsed ? 'justify-center' : ''}
                    `}
                  >
                    <span className="text-lg flex-shrink-0">{item.icon}</span>
                    {!isCollapsed && (
                      <span className="font-medium text-sm">{item.label}</span>
                    )}
                    {isActive && !isCollapsed && (
                      <div className="ml-auto w-2 h-2 bg-primary rounded-full"></div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Separator */}
          <div className="my-6 border-t border-border"></div>

          {/* External Links */}
          <div className="space-y-2">
            {!isCollapsed && (
              <p className="text-xs text-muted-foreground uppercase tracking-wider px-3 mb-3 font-semibold">
                Доп. сервисы
              </p>
            )}
            {externalLinks.map((item) => (
              <a
                key={item.href}
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <div className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-xl text-muted-foreground 
                  hover:bg-accent hover:text-accent-foreground 
                  transition-all duration-200 cursor-pointer group
                  ${isCollapsed ? 'justify-center' : ''}
                `}>
                  <span className="text-sm flex-shrink-0">{item.icon}</span>
                  {!isCollapsed && (
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{item.label}</div>
                      <div className="text-xs text-muted-foreground/70 truncate">{item.badge}</div>
                    </div>
                  )}
                  {!isCollapsed && (
                    <svg className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  )}
                </div>
              </a>
            ))}
          </div>
        </nav>

        {/* Status */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2 text-sm">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse flex-shrink-0"></div>
            {!isCollapsed && (
              <span className="text-muted-foreground text-xs">Система работает</span>
            )}
          </div>
          {!isCollapsed && (
            <div className="mt-2 text-xs text-muted-foreground/70">
              v1.0 • Прибыльная модель
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
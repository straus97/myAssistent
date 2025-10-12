import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Providers from './providers';
import Sidebar from '@/components/Sidebar';

const inter = Inter({ subsets: ['latin', 'cyrillic'] });

export const metadata: Metadata = {
  title: 'MyAssistent — Торговый Бот на ИИ',
  description: 'Прибыльная автоматическая торговля криптовалютой с искусственным интеллектом',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen bg-background">
            <Sidebar />
            <main className="lg:ml-64 transition-all duration-300">
              <div className="min-h-screen">
                {children}
              </div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}


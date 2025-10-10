# MyAssistent UI - Next.js Frontend

Modern Next.js 14 + TypeScript frontend for MyAssistent trading bot.

## Features

- 🚀 Next.js 14 with App Router
- 💎 TypeScript for type safety
- 🎨 Tailwind CSS for styling
- 🔄 React Query for data fetching
- 📊 Real-time dashboard updates
- 🌙 Dark mode support

## Getting Started

### 1. Install dependencies

```bash
npm install
```

### 2. Setup environment variables

Copy `.env.example` to `.env.local` and update:

```bash
cp .env.example .env.local
```

Edit `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your_api_key_here
```

### 3. Run development server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js 14 App Router pages
│   │   ├── page.tsx      # Dashboard (main page)
│   │   ├── layout.tsx    # Root layout
│   │   ├── providers.tsx # React Query provider
│   │   └── globals.css   # Global styles
│   ├── lib/              # Utilities
│   │   └── api.ts        # API client
│   └── components/       # Reusable components
├── public/               # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## Available Scripts

- `npm run dev` - Start development server (port 3000)
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Check TypeScript types

## API Integration

The UI communicates with the FastAPI backend at `http://localhost:8000`. 

Main API endpoints used:
- `/trade/equity` - Portfolio equity
- `/trade/positions` - Open positions
- `/signals/recent` - Recent trading signals
- `/model/health` - Model health status

See `src/lib/api.ts` for full API client implementation.

## Deployment

### Vercel (Recommended)

```bash
npm install -g vercel
vercel
```

### Docker

```bash
docker build -t myassistent-ui .
docker run -p 3000:3000 myassistent-ui
```

### Build static export

```bash
npm run build
# Output in `.next` directory
```

## TODO

- [ ] Add more charts (Recharts integration)
- [ ] Real-time WebSocket updates
- [ ] Model training UI
- [ ] Signal generation form
- [ ] Risk policy configuration
- [ ] Dark/Light theme toggle
- [ ] Mobile responsive improvements

## License

MIT


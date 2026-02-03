#!/bin/bash
echo "════════════════════════════════════════════════════════"
echo "📊 MyAssistent Trading Bot - Status Check"
echo "🕐 $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "════════════════════════════════════════════════════════"
echo ""

API_KEY="5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73"

echo "💰 EQUITY & POSITIONS:"
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/paper-monitor/status | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  Cash: \${d['equity']['cash']:.2f}\n  Positions Value: \${d['equity']['positions_value']:.2f}\n  Total Equity: \${d['equity']['equity']:.2f}\n  PnL: \${d['equity']['equity']-10000:.2f} ({(d['equity']['equity']/10000-1)*100:.2f}%)\n  Open Positions: {d['positions_count']}\n  Total Signals: {d['stats']['total_signals']}\n  Last Update: {d['last_update']}\")"

echo ""
echo "📈 OPEN POSITIONS:"
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/trade/positions | \
  python3 -c "import sys, json; positions=json.load(sys.stdin)['positions']; [print(f\"  {p['symbol']}: {p['qty']:.6f} @ \${p['avg_price']:.2f} (opened {p['opened_at'][:19]})\") for p in positions] if positions else print('  No open positions')"

echo ""
echo "🔔 RECENT SIGNALS (Last 3):"
curl -s -H "X-API-Key: $API_KEY" "http://localhost:8000/signals/recent?limit=3" | \
  python3 -c "import sys, json; signals=json.load(sys.stdin); [print(f\"  {s['created_at'][:19]} | {s['symbol']}: {s['signal'].upper()} (prob {s['prob_up']:.2%})\") for s in signals[:3]]"

echo ""
echo "🏥 SYSTEM HEALTH:"
curl -s http://localhost:8000/health | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  Status: {d['status']}\n  Database: {d['services']['database']}\n  Scheduler: {d['services']['scheduler']}\n  Model: {d['services']['model']}\")"

echo ""
echo "════════════════════════════════════════════════════════"

# Nivesh Frontend

Professional-grade React 19 SPA for financial analytics and portfolio management.

## 🚀 Quick Start

```bash
npm install
npm run dev
```

**Local Server:** http://localhost:5173

## 📦 Build

```bash
npm run build    # Production build → dist/
npm run preview  # Preview production build locally
npm run lint     # Run ESLint
```

## 🏗️ Architecture

**Tech Stack:**
- React 19 with Vite 8 (fast HMR)
- Redux Toolkit for state management (4 slices: funds, stocks, sync, compare)
- Tailwind CSS with custom **Califino Design System** tokens
- Axios for API communication with JWT auto-injection

**Key Components:**
- **Pages:** Dashboard, MF Listing/Detail/Compare, Stock Listing/Detail/Compare, Screener, Portfolio
- **Components:** Reusable cards, charts, tables, filters, comparison panels
- **Store:** Redux slices for funds, stocks, metrics sync, comparisons
- **Services:** API layer with per-resource service modules (fundService.js, stockService.js, etc.)

## 🎨 Design System

**Califino** — Premium glassmorphism-based design system:
- **Colors:** Gold accents (#e9c349), Emerald highlights (#66dd8b), Dark backgrounds
- **Effects:** Glass-morphism (rgba with blur), smooth transitions, depth shadows
- **Responsive:** Mobile-first, 3-column grid on desktop (fund/stock cards)

See [Nivesh Design System](../docs/FRONTEND.md) for detailed tokens and patterns.

## 🔄 State Management

**Redux Slices:**
- `fundsSlice` — Fund list, detail, filters, pagination
- `stocksSlice` — Stock list, detail, filters, search
- `syncSlice` — Metrics computation status (JIT polling)
- `compareSlice` — Comparison state for funds/stocks

## 🔐 Authentication

JWT tokens stored in React Context (`AuthContext`). Axios interceptor auto-injects `Authorization` header on all requests.

## 📚 Documentation

- **[System Overview](../docs/OVERVIEW.md)** — Full architecture and design
- **[Frontend Deep Dive](../docs/FRONTEND.md)** — Component details, state patterns, design tokens
- **[API Reference](../docs/API_REFERENCE.md)** — All REST endpoints

## ⚙️ Development

See [CLAUDE.md](../CLAUDE.md) for local development commands and project conventions.

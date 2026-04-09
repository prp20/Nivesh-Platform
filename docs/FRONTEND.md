# Frontend Architecture & Design

The Nivesh Elite frontend is built with a focus on **visual excellence** and **responsive performance**, adhering to the **CALIFINO** design system.

## 🎨 Tech Stack
- **Framework**: React 19 (Vite 8)
- **State Management**: Redux Toolkit (4 slices), React Context (Auth, Theme)
- **Styling**: Vanilla CSS (CALIFINO custom tokens)
- **Networking**: Axios (intercepted for JWT auth)
- **Visualization**: Recharts

---

## 🏗️ Project Structure
```text
frontend/
├── src/
│   ├── api/          # Centralized Axios client & services (authService, fundService)
│   ├── components/   # UI elements (Navbar, BottomNavBar, Layout)
│   ├── context/      # Context State (AuthContext, ThemeContext)
│   ├── store/
│   │   └── slices/
│   │       ├── syncSlice.js     # Fund & Index background sync jobs
│   │       ├── compareSlice.js  # Global compare dock (up to 4 funds)
│   │       ├── fundsSlice.js    # MFListing data, pagination, filters
│   │       └── indicesSlice.js  # IndicesListing data, pagination, search
│   ├── pages/        # Route-level views
│   ├── assets/       # Global styles and static assets
│   └── App.jsx       # Hash-based router and layout wrapper
```

---

## ⚡ Key Features

### 1. Just-In-Time (JIT) Sync
Triggered via Redux thunks. When a metric request (404) occurs, the UI feedback loop initiates a computation request on the backend and polls for status every 3 seconds. Supported for **both fund** and **index** entities.

### 2. Equity Intelligence Suite
The frontend provides a comprehensive stock analysis toolkit:
- **Screener**: Dynamic filtering across 17+ fundamental ratios with real-time server-side pagination.
- **Stock Detail**: Professional level snapshots containing technical indicators (RSI, MACD), OHLCV charts, and normalized financial statements.
- **Stock Compare**: Side-by-side fundamental matrix for up to 5 equities.

### 3. State Management
| Slice | Purpose |
|---|---|
| `syncSlice` | Background sync job tracking (MFs & Indices) |
| `compareSlice` | Cross-page fund compare dock (max 4 funds) |
| `fundsSlice` | MF listing, pagination, and multi-category filters |
| `indicesSlice` | Benchmark data and historical NAV searching |
| `stocksSlice` | Stock master list, sector filtering, and paginated screener results |

### 4. Routing
Custom hash-based router in `App.jsx` using a `hashchange` event listener. This lightweight implementation ensures maximum performance and zero dependency overhead.

---

## 🏗️ Technical Details

### State Flow
- **Axios Interceptors**: Automatically inject `Authorization: Bearer` from `AuthContext` and handle 401 token expirations.
- **Polling Logic**: The frontend polls `GET /api/v1/metrics/{code}/status` every 3s until a sync job reaches COMPLETED/FAILED.
- **Screener Filters**: The `Screener.jsx` page dispatches `fetchScreenerResults(filters)` which constructs a complex query string for the backend's dynamic WHERE clause.

---

## ⚠️ Known Limitations / Road Map
- **Portfolio page**: Manual entry integrated; holdings backend API integration pending.
- **Live WebSocket Feed**: Real-time price updates planned for Phase 5.

---

## 🎨 Design System (Nivesh Elite)

### Color Palette

| Token | Hex | Usage |
|---|---|---|
| Primary (Gold) | `#e9c349` | Accents, highlights, hero elements |
| Secondary (Emerald) | `#66dd8b` | Interactive elements, success states |
| Background | `#0f1419` | Dark navy main canvas |
| Surface Container | `#1b2025` | Card backgrounds |
| On-Surface | `#dee3ea` | Primary text (high contrast) |
| On-Surface-Variant | `#c6c6cc` | Secondary text, labels |
| Error | `#ffb4ab` | Losses, destructive actions |

### Effects & Styling

- **Glassmorphism**: `rgba(48, 53, 59, 0.6)` background + `backdrop-filter: blur(20px)` on all cards/panels
- **Glass borders**: Top/left `1px solid rgba(69, 70, 76, 0.2)` for frosted edge
- **Hover state**: `translateY(-4px)`, opacity 0.6 → 0.7, transition 300ms
- **Gold gradient**: `linear-gradient(135deg, #e9c349 0%, #9d7e00 100%)` for hero accents
- **Emerald glow**: `drop-shadow(0 0 8px rgba(102, 221, 139, 0.1))` for highlights

### Typography

- **Manrope** (600–800 weight): Headlines, body text (`font-headline`, `font-body`)
- **Inter** (300–600 weight): Labels, small UI text (`font-label`)
- Scale: `h1` 2.25rem bold, `h3` 1.125rem bold, label 0.75rem uppercase tracked

### Component Patterns

- **Cards**: `rounded-xl bg-surface-container` + hover scale, `border border-white/5`
- **Glass panels**: `.glass-panel` class — blur(20px) + rgba border
- **Buttons**: Gold gradient (`gold-gradient`) for primary, outlined for secondary
- **Chips/Badges**: `rounded-full` with status colors (emerald success, error loss, gold warning)
- **Tables**: Glass container with `hover:bg-white/5` row highlighting
- **Nav (active)**: `rounded-r-full bg-primary/10 text-primary px-8`
- **Sidebar branding**: "The Sovereign Ledger / Private Tier" block at top of `SideNavBar`

---

## 🛠️ Setup & Development
```bash
cd frontend
npm install
npm run dev
```
*Note: Ensure the backend is running on port 8000 for local development.*

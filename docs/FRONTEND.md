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
Triggered via Redux thunks. When a metric request (404) occurs, the UI feedback loop initiates a computation request on the backend and polls for status every 3 seconds. Supported for **both fund** (`syncSlice.jobs`) and **index** (`syncSlice.indexJobs`) entities.

### 2. State Management
| Slice | Pages That Use It | Purpose |
|---|---|---|
| `syncSlice` | Dashboard, MFDetail, IndexDetail | Background sync job tracking |
| `compareSlice` | MFListing, MFCompare | Cross-page compare dock (max 4 funds) |
| `fundsSlice` | MFListing | Fund list, pagination, category/AMC filters |
| `indicesSlice` | IndicesListing | Index list, pagination, search |
| `AuthContext` | All | User sessions, JWT storage |
| `ThemeContext` | App-level | Global dark mode token switching |

### 3. Routing
Custom hash-based router in `App.jsx` using a `hashchange` event listener. No `react-router-dom` dependency.

### 4. Navigation
- **Top Navbar**: Desktop — brand logo + page links.
- **Bottom NavBar**: Mobile/tablet — active tab reflects current hash, reactively updated via `hashchange` listener.

### 5. Benchmark CSV Ingestion
The **Index Detail** page allows direct CSV upload for historical NAV data. Parses and submits records to the backend with immediate chart refresh.

---

## ⚠️ Known Limitations / Pending Integration
- **Portfolio page**: Placeholder only. Holdings backend API not yet integrated.
- **Stocks pages** (StockListing, StockDetail): Placeholder only. NSE/BSE live feed integration pending.

---

## 🗂️ State Management (All Slices)

**Redux slices** own server data:
- `fundsSlice` — MF listing, detail, filtering, pagination
- `syncSlice` — job polling (JIT sync)
- `compareSlice` — up to 4 funds for comparison
- `indicesSlice` — benchmarks (Nifty indices)
- `stocksSlice` — stock listing, detail, screener, filters (sector, market_cap, rating, financial ratios)

**Context** owns session state: `AuthContext` (JWT, login/logout), `ThemeContext` (dark mode tokens).

- Axios client (`src/api/`) injects `Authorization: Bearer` from `AuthContext` automatically.
- The frontend polls `GET /api/v1/metrics/{code}/status` every 3 s until a sync job reaches COMPLETED/FAILED (JIT sync pattern).
- Stock listing page uses `dispatch(fetchStocks(filters))` with pagination + sector filtering.

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

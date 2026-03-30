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

## 🛠️ Setup & Development
```bash
cd frontend
npm install
npm run dev
```
*Note: Ensure the backend is running on port 8000 for local development.*

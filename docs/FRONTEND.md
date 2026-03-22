# Frontend Architecture & Design

The Nivesh Elite frontend is built with a focus on **visual excellence** and **responsive performance**, adhering to the **CALIFINO** design system.

## 🎨 Design Philosophy: CALIFINO
- **Permanent Dark Mode**: Optimized for financial focus and reduced eye strain.
- **Glassmorphism**: Subtle translucent backgrounds and blurs for a premium feel.
- **Micro-Animations**: Spring-based transitions and hover effects to guide user attention.
- **Typography**: High-legibility sans-serif fonts with strict hierarchical scaling.

---

## 🏗️ Project Structure
```text
frontend/
├── src/
│   ├── api/          # Centralized Axios client & services
│   ├── components/   # Atomic & reusable UI elements
│   ├── context/      # Global state (Auth, Theme)
│   ├── pages/        # Route-level views (Dashboard, MFListing)
│   ├── assets/       # Global styles and static files
│   └── App.jsx       # Main router and layout wrapper
```

---

## ⚡ Key Features

### 1. Just-In-Time (JIT) Sync
The frontend intelligently handles cases where financial data might be missing. If a request for metrics returns a 404, the UI provides feedback while the backend triggers an automatic synchronization and computation in the background.

### 2. State Management
- **AuthContext**: Manages user sessions, JWT storage, and protected routes.
- **ThemeContext**: Handles global styling tokens and (future) palette switches.

### 3. Navigation
- **Top Navbar**: Primary desktop navigation.
- **Bottom Navigation**: Optimized for mobile and tablet touch interaction.

---

## 🛠️ Setup & Development
```bash
cd frontend
npm install
npm run dev
```
*Note: Ensure the backend is running on port 8000 for local development.*

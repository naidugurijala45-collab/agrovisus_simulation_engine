import { Bug, FileText, FlaskConical, LayoutDashboard } from 'lucide-react';
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import './index.css';
import Disease from './pages/Disease';
import Landing from './pages/Landing';
import Reports from './pages/Reports';
import Simulate from './pages/Simulate';

const NAV = [
    { to: '/', label: 'Home', icon: <LayoutDashboard size={16} /> },
    { to: '/simulate', label: 'Simulation', icon: <FlaskConical size={16} /> },
    { to: '/disease', label: 'Diagnostics', icon: <Bug size={16} /> },
    { to: '/reports', label: 'Reports', icon: <FileText size={16} /> },
];

function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <h1>🌾 AgroVisus</h1>
                <span>AI Crop Platform</span>
            </div>
            <nav className="sidebar-nav">
                {NAV.map(({ to, label, icon }) => (
                    <NavLink
                        key={to}
                        to={to}
                        end={to === '/'}
                        className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                    >
                        {icon}
                        {label}
                    </NavLink>
                ))}
            </nav>
            <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
                <div className="text-sm text-muted">v1.0.0 — MVP</div>
            </div>
        </aside>
    );
}

export default function App() {
    return (
        <BrowserRouter>
            <div className="app-shell">
                <Sidebar />
                <main className="main-content">
                    <Routes>
                        <Route path="/" element={<Landing />} />
                        <Route path="/simulate" element={<Simulate />} />
                        <Route path="/disease" element={<Disease />} />
                        <Route path="/reports" element={<Reports />} />
                    </Routes>
                </main>
            </div>
        </BrowserRouter>
    );
}

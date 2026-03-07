import { Bug, ChevronLeft, ChevronRight, FileText, FlaskConical, LayoutDashboard } from 'lucide-react';
import { useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import './index.css';
import Disease from './pages/Disease';
import Landing from './pages/Landing';
import Reports from './pages/Reports';
import Simulate from './pages/Simulate';

const NAV = [
    { to: '/', label: 'Home', icon: <LayoutDashboard size={18} /> },
    { to: '/simulate', label: 'Simulation', icon: <FlaskConical size={18} /> },
    { to: '/disease', label: 'Diagnostics', icon: <Bug size={18} /> },
    { to: '/reports', label: 'Reports', icon: <FileText size={18} /> },
];

function Sidebar({ isCollapsed, onToggle }) {
    return (
        <aside className={`sidebar ${isCollapsed ? 'is-collapsed' : ''}`}>
            <div className="sidebar-logo">
                <div className="logo-text">
                    <h1>🌾 AgroVisus</h1>
                    <span>AI Crop Platform</span>
                </div>
                <button className="sidebar-toggle" onClick={onToggle} aria-label="Toggle Sidebar">
                    {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                </button>
            </div>

            <nav className="sidebar-nav">
                {NAV.map(({ to, label, icon }) => (
                    <NavLink
                        key={to}
                        to={to}
                        end={to === '/'}
                        className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                        title={isCollapsed ? label : undefined}
                    >
                        {icon}
                        <span className="nav-label">{label}</span>
                    </NavLink>
                ))}
            </nav>
            <div className="sidebar-footer">
                <div className="text-sm text-muted">v1.0.0 — MVP</div>
            </div>
        </aside>
    );
}

export default function App() {
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <BrowserRouter>
            <div className="app-shell">
                <Sidebar isCollapsed={isCollapsed} onToggle={() => setIsCollapsed(!isCollapsed)} />
                <main className={`main-content ${isCollapsed ? 'is-collapsed' : ''}`}>
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

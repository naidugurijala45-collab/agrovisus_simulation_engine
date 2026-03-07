import axios from 'axios';
import { Play, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
    Area,
    AreaChart,
    CartesianGrid,
    Legend,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis, YAxis,
} from 'recharts';
import { getCropTemplates, runSimulation } from '../api/client';
import LocationPicker from '../components/LocationPicker';

const DEFAULT_FORM = {
    crop_template: 'corn',
    sim_days: 91,
    latitude: 40.0,
    longitude: -88.0,
    elevation_m: 100.0,
};

const CHART_STYLE = {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text-primary)',
};

export default function Simulate() {
    const [form, setForm] = useState(DEFAULT_FORM);
    const [templates, setTemplates] = useState([]);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const abortControllerRef = useRef(null);

    useEffect(() => {
        getCropTemplates()
            .then((d) => setTemplates(d.templates || []))
            .catch(() => setTemplates([{ id: 'corn', name: 'Corn' }, { id: 'wheat', name: 'Wheat' }]));
    }, []);

    const handleChange = (e) => {
        const { name, value, type } = e.target;
        setForm((f) => ({ ...f, [name]: type === 'number' ? parseFloat(value) : value }));
    };

    const handleLocationChange = (lat, lng) => {
        setForm((f) => ({ ...f, latitude: lat, longitude: lng }));
    };

    const handleRun = async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        abortControllerRef.current = new AbortController();

        try {
            const data = await runSimulation(
                { ...form, management_schedule: [] },
                { signal: abortControllerRef.current.signal }
            );
            setResult(data);
        } catch (e) {
            if (axios.isCancel(e)) {
                setError('Simulation cancelled by user.');
            } else {
                setError(e.response?.data?.detail || e.message || 'Simulation failed');
            }
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
        }
    };

    const handleCancel = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    };

    // Helper to group contiguous rules
    const groupedRules = [];
    if (result?.triggered_rules) {
        // Flatten into a stream of { date, ruleName, ruleId }
        const stream = [];
        for (const day of result.triggered_rules) {
            for (const r of day.rules || []) {
                stream.push({ date: day.date, name: r.name || r.rule_id, id: r.rule_id });
            }
        }

        // Group consecutive identical rules
        let currentGroup = null;
        for (const item of stream) {
            if (!currentGroup || currentGroup.id !== item.id) {
                if (currentGroup) groupedRules.push(currentGroup);
                currentGroup = { id: item.id, name: item.name, startDate: item.date, endDate: item.date };
            } else {
                currentGroup.endDate = item.date;
            }
        }
        if (currentGroup) groupedRules.push(currentGroup);
    }

    return (
        <div>
            <div className="page-header">
                <h2>🌱 Crop Simulation</h2>
                <p>Configure your simulation parameters and run the physics-based engine.</p>
            </div>

            {/* Config Form */}
            <div className="card mb-4">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 16, marginBottom: 20 }}>
                    <div className="form-group">
                        <label className="form-label">Crop Template</label>
                        <select className="form-select" name="crop_template" value={form.crop_template} onChange={handleChange}>
                            {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                            {templates.length === 0 && <option value="corn">Corn (default)</option>}
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Simulation Days</label>
                        <input className="form-input" type="number" name="sim_days" value={form.sim_days} onChange={handleChange} min={10} max={365} />
                    </div>
                    <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                        <label className="form-label" style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                            <span>Field Location</span>
                            <span className="text-muted">Lat: {form.latitude.toFixed(4)}, Lng: {form.longitude.toFixed(4)}</span>
                        </label>
                        <LocationPicker lat={form.latitude} lng={form.longitude} onChange={handleLocationChange} />
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 12 }}>
                    {!loading ? (
                        <button className="btn btn-primary" onClick={handleRun}>
                            <Play size={16} />
                            Run Simulation
                        </button>
                    ) : (
                        <button className="btn" style={{ background: 'var(--red-glow)', border: '1px solid var(--red-400)', color: 'var(--red-400)' }} onClick={handleCancel}>
                            <Square size={16} fill="var(--red-400)" />
                            Stop Simulation
                        </button>
                    )}
                </div>
            </div>

            {error && (
                <div className="card mb-4" style={{ borderColor: 'var(--red-400)', color: 'var(--red-400)' }}>
                    ⚠ {error}
                </div>
            )}

            {loading && (
                <div className="spinner-wrap">
                    <div className="spinner" />
                    <p className="text-muted">Running {form.sim_days}-day simulation…</p>
                </div>
            )}

            {result && (
                <>
                    {/* KPI Cards */}
                    <div className="card-grid card-grid-4 mb-4">
                        {[
                            { label: 'Final Biomass', value: `${result.total_biomass_kg_ha?.toFixed(0)} kg/ha`, sub: 'Total dry matter' },
                            { label: 'Final Yield', value: `${result.final_yield_kg_ha?.toFixed(0)} kg/ha`, sub: 'Grain yield' },
                            { label: 'Total Irrigation', value: `${result.total_irrigation_mm?.toFixed(0)} mm`, sub: 'Applied water' },
                            { label: 'Max Disease', value: `${result.max_disease_severity?.toFixed(1)}%`, sub: 'Peak severity' },
                        ].map((s) => (
                            <div className="stat-tile" key={s.label}>
                                <span className="stat-label">{s.label}</span>
                                <span className="stat-value">{s.value}</span>
                                <span className="stat-sub">{s.sub}</span>
                            </div>
                        ))}
                    </div>

                    {/* Charts */}
                    <div className="card-grid card-grid-2">
                        <div className="card">
                            <h3 className="text-sm text-green mb-4">Biomass Accumulation (kg/ha)</h3>
                            <div className="chart-wrap">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={result.daily_data}>
                                        <defs>
                                            <linearGradient id="biomassGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                                        <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={11} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Area type="monotone" dataKey="biomass_kg_ha" stroke="#22c55e" fill="url(#biomassGrad)" strokeWidth={2} dot={false} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="card">
                            <h3 className="text-sm text-green mb-4">Soil Moisture (Fraction AWC)</h3>
                            <div className="chart-wrap">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={result.daily_data}>
                                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                                        <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={11} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} domain={[0, 1.2]} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Line type="monotone" dataKey="soil_moisture" stroke="#38bdf8" strokeWidth={2} dot={false} name="Soil Moisture" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="card">
                            <h3 className="text-sm text-green mb-4">Stress Factors (0–1)</h3>
                            <div className="chart-wrap">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={result.daily_data}>
                                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                                        <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={11} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} domain={[0, 1]} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)' }} />
                                        <Line type="monotone" dataKey="water_stress" stroke="#f87171" strokeWidth={2} dot={false} name="Water Stress" />
                                        <Line type="monotone" dataKey="nitrogen_stress" stroke="#fbbf24" strokeWidth={2} dot={false} name="N Stress" />
                                        <Line type="monotone" dataKey="disease_severity" stroke="#c084fc" strokeWidth={2} dot={false} name="Disease %" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="card">
                            <h3 className="text-sm text-green mb-4">Daily Temperature (°C)</h3>
                            <div className="chart-wrap">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={result.daily_data}>
                                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                                        <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={11} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Area type="monotone" dataKey="avg_temp_c" stroke="#fb923c" fill="rgba(251,146,60,0.15)" strokeWidth={2} dot={false} name="Avg Temp °C" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>

                    {/* Triggered Rules */}
                    {groupedRules.length > 0 && (
                        <div className="card mt-6">
                            <h3 className="text-sm text-green mb-4">⚡ Advisory Rules Triggered ({groupedRules.length} periods)</h3>
                            {groupedRules.map((grp, i) => (
                                <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                                    <span className="badge badge-amber" style={{ marginRight: 10 }}>
                                        {grp.startDate === grp.endDate ? grp.startDate : `${grp.startDate} to ${grp.endDate}`}
                                    </span>
                                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                        {grp.name}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}

            <style>{`.spinning { animation: spin 1s linear infinite; }`}</style>
        </div>
    );
}

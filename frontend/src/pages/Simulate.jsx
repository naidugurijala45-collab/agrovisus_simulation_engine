import axios from 'axios';
import { AlertTriangle, Play, Square, TrendingUp, XCircle } from 'lucide-react';
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
import ROIParameters from '../components/ROIParameters';
import { exportElementToPDF } from '../utils/pdfExport';

const DEFAULT_FORM = {
    crop_template: 'corn',
    sim_days: 120,
    start_date: new Date().toISOString().split('T')[0],
    latitude: 40.0,
    longitude: -88.0,
    elevation_m: 100.0,
    field_acres: 100,
    treatment_cost_per_acre: 25,
    commodity_price_usd_bu: '',
    state_code: '',
    formatted_address: '',
};

const CHART_STYLE = {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text-primary)',
};

const SEVERITY_COLOR = {
    Low: { bg: 'var(--green-glow)', text: 'var(--green-400)', border: 'rgba(74,222,128,0.25)' },
    Medium: { bg: 'var(--amber-glow)', text: 'var(--amber-400)', border: 'rgba(251,191,36,0.25)' },
    High: { bg: 'var(--red-glow)', text: 'var(--red-400)', border: 'rgba(248,113,113,0.25)' },
    Critical: { bg: 'var(--red-glow)', text: 'var(--red-400)', border: 'rgba(248,113,113,0.4)' },
};

const ROI_STRENGTH_COLOR = {
    'Strong Buy': { text: 'var(--green-400)', bg: 'var(--green-glow)', border: 'rgba(74,222,128,0.25)' },
    'Marginal': { text: 'var(--amber-400)', bg: 'var(--amber-glow)', border: 'rgba(251,191,36,0.25)' },
    'Monitor Only': { text: 'var(--text-muted)', bg: 'rgba(255,255,255,0.04)', border: 'var(--border)' },
};

function fmt$(n) { return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`; }
function fmtDec(n, d = 1) { return Number(n).toFixed(d); }

function RoiScenario({ label, pct = 0, highlight }) {
    const positive = pct >= 0;
    return (
        <div style={{
            flex: 1,
            padding: '10px 12px',
            borderRadius: 8,
            background: highlight ? 'rgba(74,222,128,0.07)' : 'rgba(255,255,255,0.02)',
            border: highlight ? '1px solid rgba(74,222,128,0.2)' : '1px solid var(--border)',
            textAlign: 'center',
        }}>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>
                {label}{highlight && ' ✦'}
            </div>
            <div style={{
                fontSize: '1.15rem', fontWeight: 700,
                color: positive ? 'var(--green-400)' : 'var(--red-400)',
            }}>
                {positive ? '+' : ''}{fmtDec(pct, 0)}%
            </div>
        </div>
    );
}

function RuleCard({ group }) {
    const sev = group.severity || 'Medium';
    const sevStyle = SEVERITY_COLOR[sev] || SEVERITY_COLOR.Medium;
    const roi = group.roi;
    const strength = roi?.recommendation_strength;
    const strengthStyle = ROI_STRENGTH_COLOR[strength] || ROI_STRENGTH_COLOR['Monitor Only'];

    return (
        <div style={{
            background: 'var(--bg-primary)',
            border: `1px solid ${sevStyle.border}`,
            borderRadius: 12,
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 12,
                padding: '14px 16px 12px',
                borderBottom: '1px solid var(--border)',
                flexWrap: 'wrap',
            }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        {/* Severity badge */}
                        <span style={{
                            fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase',
                            letterSpacing: '0.6px', padding: '3px 10px', borderRadius: 999,
                            background: sevStyle.bg, color: sevStyle.text, border: `1px solid ${sevStyle.border}`,
                        }}>
                            {sev}
                        </span>
                        {/* Alert type chip */}
                        {group.alert_type && (
                            <span style={{
                                fontSize: '0.68rem', color: 'var(--text-muted)',
                                background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
                                borderRadius: 999, padding: '3px 10px',
                            }}>
                                {group.alert_type}
                            </span>
                        )}
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {group.name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Active: {group.startDate === group.endDate
                            ? group.startDate
                            : `${group.startDate} → ${group.endDate}`}
                        {group.daysActive > 1 && (
                            <span style={{ marginLeft: 8, color: 'var(--amber-400)', fontWeight: 600 }}>
                                ({group.daysActive}d)
                            </span>
                        )}
                    </div>
                </div>

                {/* Recommendation strength pill */}
                {strength && (
                    <div style={{
                        padding: '6px 14px', borderRadius: 999,
                        background: strengthStyle.bg, color: strengthStyle.text,
                        border: `1px solid ${strengthStyle.border}`,
                        fontSize: '0.75rem', fontWeight: 700, whiteSpace: 'nowrap', alignSelf: 'flex-start',
                    }}>
                        {strength === 'Strong Buy' ? '↑ ' : strength === 'Marginal' ? '→ ' : '↓ '}
                        {strength}
                    </div>
                )}
            </div>

            {/* Recommendation text */}
            {group.recommendation && (
                <div style={{
                    padding: '10px 16px',
                    fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic',
                    borderBottom: roi ? '1px solid var(--border)' : 'none',
                }}>
                    {group.recommendation}
                </div>
            )}

            {/* ROI Block */}
            {roi && (
                <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {/* Top metrics row */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
                        {[
                            { label: 'Revenue at Risk', value: `${fmt$(roi.revenue_at_risk_per_acre)}/acre`, sub: `${fmt$(roi.revenue_at_risk_total)} total`, color: 'var(--red-400)' },
                            { label: 'Yield Loss', value: `${fmtDec(roi.estimated_yield_loss_bu_acre)} bu/acre`, sub: 'without treatment', color: 'var(--amber-400)' },
                            { label: 'Treatment Cost', value: `${fmt$(roi.treatment_cost_total)} total`, sub: `${fmt$(roi.treatment_cost_total / Math.max(1, roi.revenue_at_risk_total / Math.max(0.01, roi.revenue_at_risk_per_acre)))}/acre`, color: 'var(--text-secondary)' },
                        ].map(m => (
                            <div key={m.label} style={{
                                padding: '10px 12px', borderRadius: 8,
                                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
                            }}>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{m.label}</div>
                                <div style={{ fontSize: '0.95rem', fontWeight: 700, color: m.color }}>{m.value}</div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2 }}>{m.sub}</div>
                            </div>
                        ))}
                    </div>

                    {/* ROI scenarios */}
                    <div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <TrendingUp size={12} />
                            Treatment ROI (by fungicide/treatment efficacy)
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <RoiScenario label="Low (50%)" pct={roi.roi_low} />
                            <RoiScenario label="Medium (70%)" pct={roi.roi_mid} highlight />
                            <RoiScenario label="High (90%)" pct={roi.roi_high} />
                        </div>
                    </div>

                    {/* Breakeven */}
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '8px 12px', borderRadius: 8,
                        background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
                        fontSize: '0.78rem', color: 'var(--text-muted)',
                    }}>
                        <AlertTriangle size={13} color="var(--amber-400)" />
                        Treatment breaks even at <strong style={{ color: 'var(--text-secondary)', margin: '0 4px' }}>
                            {fmtDec(roi.breakeven_yield_loss_percent, 1)}% yield loss
                        </strong> (medium efficacy assumption)
                    </div>
                </div>
            )}
        </div>
    );
}

export default function Simulate() {
    const [form, setForm] = useState(() => {
        try {
            const saved = sessionStorage.getItem('agrovisus_sim_form');
            return saved ? { ...DEFAULT_FORM, ...JSON.parse(saved) } : DEFAULT_FORM;
        } catch {
            return DEFAULT_FORM;
        }
    });
    const [templates, setTemplates] = useState([]);
    const [result, setResult] = useState(() => {
        try {
            const saved = sessionStorage.getItem('agrovisus_sim_result');
            return saved ? JSON.parse(saved) : null;
        } catch {
            return null;
        }
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const abortControllerRef = useRef(null);
    const reportRef = useRef(null);

    useEffect(() => {
        try { sessionStorage.setItem('agrovisus_sim_form', JSON.stringify(form)); } catch {}
    }, [form]);

    useEffect(() => {
        try {
            if (result) sessionStorage.setItem('agrovisus_sim_result', JSON.stringify(result));
            else sessionStorage.removeItem('agrovisus_sim_result');
        } catch {}
    }, [result]);

    useEffect(() => {
        getCropTemplates()
            .then((d) => setTemplates(d.templates || []))
            .catch(() => setTemplates([{ id: 'corn', name: 'Corn' }, { id: 'wheat', name: 'Wheat' }]));
    }, []);

    const handleChange = (e) => {
        const { name, value, type } = e.target;
        setForm((f) => ({ ...f, [name]: type === 'number' ? (value === '' ? '' : parseFloat(value)) : value }));
    };

    const handleLocationChange = (lat, lng, meta = {}) => {
        setForm((f) => ({ ...f, latitude: lat, longitude: lng, ...meta }));
    };

    const handleRun = async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        abortControllerRef.current = new AbortController();
        try {
            const payload = {
                ...form,
                management_schedule: [],
                state_code: form.state_code || null,
                field_acres: parseFloat(form.field_acres) || 100,
                treatment_cost_per_acre: parseFloat(form.treatment_cost_per_acre) || 25,
                commodity_price_usd_bu: form.commodity_price_usd_bu !== '' ? parseFloat(form.commodity_price_usd_bu) : null,
            };
            const data = await runSimulation(payload, { signal: abortControllerRef.current.signal });
            setResult(data);
        } catch (e) {
            if (axios.isCancel(e)) setError('Simulation cancelled.');
            else setError(e.response?.data?.detail || e.message || 'Simulation failed');
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
        }
    };

    const handleCancel = () => abortControllerRef.current?.abort();

    const handleExportPDF = async () => {
        if (!reportRef.current) return;
        const ok = await exportElementToPDF(reportRef.current, `agrovisus-sim-report-${form.start_date || 'latest'}.pdf`);
        if (!ok) setError('Failed to generate PDF.');
    };

    // Build grouped rules with full rule data attached
    const groupedRules = [];
    if (result?.triggered_rules) {
        const stream = [];
        for (const day of result.triggered_rules) {
            for (const r of day.rules || []) {
                stream.push({
                    date: day.date,
                    lastTriggered: day.last_triggered || day.date,
                    daysActive: day.days_active || 1,
                    rule: r,
                });
            }
        }
        // Backend already deduplicates by rule_id; each day-entry is unique.
        // last_triggered and days_active come from the backend dedup pass.
        for (const item of stream) {
            groupedRules.push({
                id: item.rule.rule_id,
                name: item.rule.name || item.rule.rule_id,
                severity: item.rule.severity,
                alert_type: item.rule.alert_type,
                recommendation: item.rule.recommendation,
                roi: item.rule.roi,
                startDate: item.date,
                endDate: item.lastTriggered || item.date,
                daysActive: item.daysActive || 1,
            });
        }
    }

    return (
        <div>
            <div className="page-header">
                <h2>🌱 Crop Simulation</h2>
                <p>Configure your simulation parameters and run the physics-based engine.</p>
            </div>

            {/* Config Form */}
            <div className="card mb-4">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 16, marginBottom: 16 }}>
                    <div className="form-group">
                        <label className="form-label">Crop Template</label>
                        <select className="form-select" name="crop_template" value={form.crop_template} onChange={handleChange}>
                            {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                            {templates.length === 0 && <option value="corn">Corn (default)</option>}
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Start Date</label>
                        <input className="form-input" type="date" name="start_date" value={form.start_date} onChange={handleChange} />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Simulation Days</label>
                        <input className="form-input" type="number" name="sim_days" value={form.sim_days} onChange={handleChange} min={10} max={365} />
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>Recommended: 120+ days for a full season</span>
                    </div>
                    <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                        <label className="form-label" style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                            <span>Field Location</span>
                            <span className="text-muted">Lat: {form.latitude.toFixed(4)}, Lng: {form.longitude.toFixed(4)}</span>
                        </label>
                        <LocationPicker
                                            lat={form.latitude}
                                            lng={form.longitude}
                                            onChange={handleLocationChange}
                                            resolved={{ formatted_address: form.formatted_address, state_code: form.state_code }}
                                        />
                    </div>
                </div>

                {/* ROI Inputs */}
                <div style={{ marginBottom: 20 }}>
                    <ROIParameters
                        fieldAcres={form.field_acres}
                        treatmentCostPerAcre={form.treatment_cost_per_acre}
                        commodityPrice={form.commodity_price_usd_bu}
                        onChange={(key, value) => setForm(f => ({ ...f, [key]: value }))}
                    />
                </div>

                <div style={{ display: 'flex', gap: 12 }}>
                    {!loading ? (
                        <button className="btn btn-primary" onClick={handleRun}>
                            <Play size={16} /> Run Simulation
                        </button>
                    ) : (
                        <button className="btn" style={{ background: 'var(--red-glow)', border: '1px solid var(--red-400)', color: 'var(--red-400)' }} onClick={handleCancel}>
                            <Square size={16} fill="var(--red-400)" /> Stop Simulation
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
                <div ref={reportRef} style={{ background: 'var(--bg-primary)', padding: '20px 0' }}>
                    <div className="pdf-only-title" style={{ display: 'none' }}>
                        <h2 style={{ margin: 0, color: 'var(--green-400)' }}>AgroVisus Platform</h2>
                        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Simulation Report: {templates.find(t => t.id === form.crop_template)?.name || form.crop_template}</p>
                        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Generated: {new Date().toLocaleDateString()}</p>
                    </div>

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

                    {/* Triggered Rules with ROI */}
                    {groupedRules.length > 0 && (
                        <div className="card mt-6">
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
                                <h3 className="text-sm text-green">
                                    ⚡ Advisory Alerts — {groupedRules.length} rule{groupedRules.length > 1 ? 's' : ''} triggered
                                </h3>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                    {form.field_acres} acres · ${form.treatment_cost_per_acre}/acre treatment cost
                                </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                {groupedRules.map((grp, i) => <RuleCard key={i} group={grp} />)}
                            </div>
                        </div>
                    )}

                    {groupedRules.length === 0 && (
                        <div className="card mt-6" style={{ textAlign: 'center', padding: '32px 24px' }}>
                            <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>✅</div>
                            <div style={{ color: 'var(--green-400)', fontWeight: 600, marginBottom: 4 }}>No advisory alerts triggered</div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Conditions stayed within acceptable thresholds throughout the simulation.</div>
                        </div>
                    )}

                    {/* ACTION BAR */}
                    <div className="action-bar mt-8" data-html2canvas-ignore="true">
                        <button
                            className="btn btn-outline"
                            style={{ borderColor: 'var(--red-400)', color: 'var(--red-400)' }}
                            onClick={() => setResult(null)}
                        >
                            <XCircle size={18} /> Clear Results
                        </button>
                        <div style={{ flexGrow: 1 }} />
                        <button
                            className="btn btn-outline"
                            onClick={() => alert('Cloud Sync is coming in an upcoming update! For now, please use the PDF export.')}
                        >
                            Save to Dashboard
                        </button>
                        <button className="btn btn-primary" onClick={handleExportPDF}>
                            Download PDF Report
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

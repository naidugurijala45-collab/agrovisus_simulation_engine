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
    ReferenceLine,
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
    initial_growth_stage: 'V8',
    soil_nitrogen_ppm: 25,
    soil_moisture_level: 'normal',
    recent_rain_event: false,
};

const CHART_STYLE = {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text-primary)',
};

const SEVERITY_COLOR = {
    Low:      { bg: 'rgba(74,222,128,0.15)',  text: '#4ade80',  border: 'rgba(74,222,128,0.35)' },
    Medium:   { bg: 'rgba(251,191,36,0.15)',  text: '#fbbf24',  border: 'rgba(251,191,36,0.35)' },
    Moderate: { bg: 'rgba(251,191,36,0.15)',  text: '#fbbf24',  border: 'rgba(251,191,36,0.35)' },
    High:     { bg: 'rgba(239,68,68,0.18)',   text: '#f87171',  border: 'rgba(239,68,68,0.40)' },
    Critical: { bg: 'rgba(239,68,68,0.28)',   text: '#fca5a5',  border: 'rgba(239,68,68,0.55)' },
};

const ROI_STRENGTH_COLOR = {
    'Strong Buy': { text: 'var(--green-400)', bg: 'var(--green-glow)', border: 'rgba(74,222,128,0.25)' },
    'Marginal': { text: 'var(--amber-400)', bg: 'var(--amber-glow)', border: 'rgba(251,191,36,0.25)' },
    'Monitor Only': { text: 'var(--text-muted)', bg: 'rgba(255,255,255,0.04)', border: 'var(--border)' },
};

const SOIL_MOISTURE_MAP = { dry: 0.4, normal: 0.85, wet: 0.95 };

function fmt$(n) { return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`; }
function fmtDec(n, d = 1) { return Number(n).toFixed(d); }
function fmtDate(dateStr) {
    if (!dateStr) return '';
    // Append T00:00:00 to force local-time parsing — bare YYYY-MM-DD is parsed
    // as UTC midnight which shifts the displayed date in non-UTC timezones.
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
function fmtDateFull(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function kgHaToBuAcre(kg_ha) { return (kg_ha || 0) / 62.77; }

const GRADE_STYLE = {
    A: { color: '#22c55e', label: 'Excellent' },
    B: { color: '#84cc16', label: 'Good' },
    C: { color: '#f59e0b', label: 'Moderate Stress' },
    D: { color: '#f97316', label: 'High Stress' },
    F: { color: '#ef4444', label: 'Critical' },
};

function getFieldHealthGrade(yieldKgHa, highAlerts, modAlerts) {
    const bu = kgHaToBuAcre(yieldKgHa);
    if (bu < 80) return 'F';
    if (highAlerts >= 2 || bu < 110) return 'D';
    if (highAlerts >= 1 || bu < 140) return 'C';
    if (highAlerts === 0 && bu > 170 && modAlerts <= 1) return 'A';
    return 'B';
}

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

function RuleCard({ group, fieldAcres = 100, treatmentCostPerAcre = 25 }) {
    const sev = group.severity || 'Moderate';
    const sevStyle = SEVERITY_COLOR[sev] || SEVERITY_COLOR.Moderate;
    const roi = group.roi;
    const strength = roi?.recommendation_strength;
    const strengthStyle = ROI_STRENGTH_COLOR[strength] || ROI_STRENGTH_COLOR['Monitor Only'];

    return (
        <div style={{
            background: 'var(--bg-primary)',
            border: `1px solid ${sevStyle.border}`,
            borderLeft: `4px solid ${sevStyle.text}`,
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
                            ? fmtDateFull(group.startDate)
                            : `${fmtDateFull(group.startDate)} → ${fmtDateFull(group.endDate)}`}
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
                            { label: 'Treatment Cost', value: `${fmt$(treatmentCostPerAcre)}/acre × ${fieldAcres} acres`, sub: `= ${fmt$(roi.treatment_cost_total)} total`, color: 'var(--text-secondary)' },
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
    const [activeScenario, setActiveScenario] = useState(null);
    const [scenario1Result, setScenario1Result] = useState(null); // Problem Field
    const [scenario2Result, setScenario2Result] = useState(null); // Well-Managed
    const [pendingScenario, setPendingScenario] = useState(null); // 'problem' | 'wellManaged'
    const [weatherStripOpen, setWeatherStripOpen] = useState(false);

    const [fertEvents, setFertEvents] = useState([{ id: 1, day: 7, amount: 80, fertType: 'urea' }]);
    const [irrigEvents, setIrrigEvents] = useState([]);
    const [newFert, setNewFert] = useState({ day: '', amount: '', fertType: 'urea' });
    const [newIrrig, setNewIrrig] = useState({ day: '', amount: '' });

    const abortControllerRef = useRef(null);
    const reportRef = useRef(null);

    const addFertEvent = () => {
        const day = parseInt(newFert.day);
        const amount = parseFloat(newFert.amount);
        if (!day || !amount || day < 1 || day > 150) return;
        setFertEvents(prev => [...prev, { id: Date.now(), day, amount, fertType: newFert.fertType }]);
        setNewFert({ day: '', amount: '', fertType: 'urea' });
    };
    const removeFertEvent = (id) => setFertEvents(prev => prev.filter(e => e.id !== id));

    const addIrrigEvent = () => {
        const day = parseInt(newIrrig.day);
        const amount = parseFloat(newIrrig.amount);
        if (!day || !amount || day < 1 || day > 150) return;
        setIrrigEvents(prev => [...prev, { id: Date.now(), day, amount }]);
        setNewIrrig({ day: '', amount: '' });
    };
    const removeIrrigEvent = (id) => setIrrigEvents(prev => prev.filter(e => e.id !== id));

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
        const { name, value, type, checked } = e.target;
        setActiveScenario(null);
        setForm((f) => ({
            ...f,
            [name]: type === 'checkbox' ? checked
                  : type === 'number'   ? (value === '' ? '' : parseFloat(value))
                  : value,
        }));
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
                management_schedule: [
                    ...fertEvents.map(e => ({ type: 'fertilizer', day: e.day, amount_kg_ha: e.amount, fertilizer_type: e.fertType })),
                    ...irrigEvents.map(e => ({ type: 'irrigation', day: e.day, amount_mm: e.amount })),
                ].sort((a, b) => a.day - b.day),
                state_code: form.state_code || null,
                field_acres: parseFloat(form.field_acres) || 100,
                treatment_cost_per_acre: parseFloat(form.treatment_cost_per_acre) || 25,
                commodity_price_usd_bu: form.commodity_price_usd_bu !== '' ? parseFloat(form.commodity_price_usd_bu) : null,
                soil_nitrogen_ppm: parseFloat(form.soil_nitrogen_ppm) || 25,
                soil_water_factor: SOIL_MOISTURE_MAP[form.soil_moisture_level] ?? 0.85,
                recent_rain_event: Boolean(form.recent_rain_event),
            };
            const data = await runSimulation(payload, { signal: abortControllerRef.current.signal });
            setResult(data);
            if (pendingScenario === 'problem') {
                setScenario1Result({ ...data, _form: { commodity_price_usd_bu: payload.commodity_price_usd_bu, field_acres: payload.field_acres } });
            } else if (pendingScenario === 'wellManaged') {
                setScenario2Result({ ...data, _form: { commodity_price_usd_bu: payload.commodity_price_usd_bu, field_acres: payload.field_acres } });
            }
            setPendingScenario(null);
        } catch (e) {
            if (axios.isCancel(e)) setError('Simulation cancelled.');
            else setError(e.response?.data?.detail || e.message || 'Simulation failed');
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
        }
    };

    const handleCancel = () => abortControllerRef.current?.abort();

    const handleLoadScenario1 = () => {
        setForm({
            ...DEFAULT_FORM,
            crop_template:           'corn',
            start_date:              '2025-05-01',
            sim_days:                120,
            latitude:                40.0,
            longitude:               -89.0,
            initial_growth_stage:    'V8',
            soil_nitrogen_ppm:       10,
            soil_moisture_level:     'dry',
            recent_rain_event:       true,
            field_acres:             100,
            treatment_cost_per_acre: 25,
            commodity_price_usd_bu:  4.5,
        });
        setFertEvents([]);
        setIrrigEvents([]);
        setActiveScenario('🌽 Problem Field — Drought + N Deficiency');
        setPendingScenario('problem');
    };

    const handleLoadScenario2 = () => {
        setForm({
            ...DEFAULT_FORM,
            crop_template:           'corn',
            start_date:              '2025-05-01',
            sim_days:                120,
            latitude:                40.0,
            longitude:               -89.0,
            initial_growth_stage:    'V8',
            soil_nitrogen_ppm:       45,
            soil_moisture_level:     'normal',
            recent_rain_event:       false,
            field_acres:             100,
            treatment_cost_per_acre: 25,
            commodity_price_usd_bu:  4.5,
        });
        setFertEvents([{ id: 1, day: 7, amount: 120, fertType: 'urea' }]);
        setIrrigEvents([]);
        setActiveScenario('✅ Well-Managed Field — Optimal Management');
        setPendingScenario('wellManaged');
    };

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
                <div className="scenario-btn-row" style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 12 }}>
                    <button
                        type="button"
                        onClick={handleLoadScenario1}
                        title="V8 corn — dry soil, low nitrogen, recent heavy rain"
                        style={{
                            background: '#b45309', color: '#fff', border: 'none',
                            borderRadius: 6, padding: '6px 14px', cursor: 'pointer',
                            fontSize: 13, fontWeight: 600,
                        }}
                    >
                        🌽 Problem Field
                    </button>
                    <button
                        type="button"
                        onClick={handleLoadScenario2}
                        title="V8 corn — normal moisture, adequate nitrogen, no stress"
                        style={{
                            background: '#15803d', color: '#fff', border: 'none',
                            borderRadius: 6, padding: '6px 14px', cursor: 'pointer',
                            fontSize: 13, fontWeight: 600,
                        }}
                    >
                        ✅ Well-Managed Field
                    </button>
                </div>
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

                {/* ── Current Growth Stage ─────────────────────────────── */}
                <div style={{ marginBottom: 20 }}>
                    <div style={{
                        fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                        color: 'var(--text-muted)', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                        <span>Current Growth Stage</span>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                    </div>
                    <div style={{ maxWidth: 280 }}>
                        <label className="form-label">Growth Stage</label>
                        <select
                            className="form-select"
                            name="initial_growth_stage"
                            value={form.initial_growth_stage}
                            onChange={handleChange}
                        >
                            <optgroup label="Vegetative">
                                {['VE','V1','V2','V3','V4','V5','V6','V7','V8','V9','V10','V11','V12'].map(s => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </optgroup>
                            <optgroup label="Reproductive">
                                {[
                                    ['R1', 'R1 (Silking)'],
                                    ['R2', 'R2 (Blister)'],
                                    ['R3', 'R3 (Milk)'],
                                    ['R4', 'R4 (Dough)'],
                                    ['R5', 'R5 (Dent)'],
                                    ['R6', 'R6 (Maturity)'],
                                ].map(([val, lbl]) => (
                                    <option key={val} value={val}>{lbl}</option>
                                ))}
                            </optgroup>
                        </select>
                    </div>
                </div>

                {/* ── Soil Conditions ──────────────────────────────────── */}
                <div style={{ marginBottom: 20 }}>
                    <div style={{
                        fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                        color: 'var(--text-muted)', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                        <span>Soil Conditions</span>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20 }}>
                        {/* Soil Nitrogen */}
                        <div className="form-group" style={{ margin: 0 }}>
                            <label className="form-label">Soil Nitrogen (ppm)</label>
                            <input
                                className="form-input"
                                type="number"
                                name="soil_nitrogen_ppm"
                                value={form.soil_nitrogen_ppm}
                                onChange={handleChange}
                                min={0} max={300}
                            />
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                                Typical range: 10–40 ppm. Below 15 ppm = deficient
                            </span>
                        </div>

                        {/* Soil Moisture — segmented control */}
                        <div style={{ margin: 0 }}>
                            <label className="form-label">Soil Moisture</label>
                            <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                                {[
                                    { level: 'dry',    label: 'Dry (stressed)' },
                                    { level: 'normal', label: 'Normal' },
                                    { level: 'wet',    label: 'Wet (excess)' },
                                ].map(({ level, label }) => {
                                    const active = form.soil_moisture_level === level;
                                    return (
                                        <button
                                            key={level}
                                            type="button"
                                            onClick={() => setForm(f => ({ ...f, soil_moisture_level: level }))}
                                            style={{
                                                flex: 1,
                                                padding: '8px 4px',
                                                border: active ? '1px solid var(--green-400)' : '1px solid var(--border)',
                                                borderRadius: 6,
                                                background: active ? 'rgba(74,222,128,0.1)' : 'rgba(255,255,255,0.02)',
                                                color: active ? 'var(--green-400)' : 'var(--text-muted)',
                                                fontSize: '0.75rem',
                                                fontWeight: active ? 700 : 400,
                                                cursor: 'pointer',
                                                transition: 'all 0.15s',
                                            }}
                                        >
                                            {label}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    {/* Recent Heavy Rain — toggle */}
                    <div style={{ marginTop: 16 }}>
                        <div
                            onClick={() => setForm(f => ({ ...f, recent_rain_event: !f.recent_rain_event }))}
                            style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', width: 'fit-content' }}
                        >
                            <div style={{
                                width: 38, height: 22, borderRadius: 11, position: 'relative', flexShrink: 0,
                                background: form.recent_rain_event ? 'var(--green-400)' : 'var(--border)',
                                transition: 'background 0.2s',
                            }}>
                                <div style={{
                                    position: 'absolute', top: 3,
                                    left: form.recent_rain_event ? 19 : 3,
                                    width: 16, height: 16, borderRadius: '50%', background: 'white',
                                    transition: 'left 0.2s',
                                }} />
                            </div>
                            <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', userSelect: 'none' }}>
                                Heavy rain in last 3 days (&gt;1.5 inches)
                            </span>
                        </div>
                        {form.recent_rain_event && (
                            <div style={{
                                marginTop: 8, fontSize: '0.75rem', color: '#fbbf24', fontWeight: 600,
                                display: 'flex', alignItems: 'center', gap: 6,
                            }}>
                                ⚠ N leaching risk elevated
                            </div>
                        )}
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

                {/* Field Management */}
                <div style={{ marginBottom: 20 }}>
                    <div style={{
                        fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                        color: 'var(--text-muted)', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                        <span>Field Management</span>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                    </div>

                    {/* Fertilizer */}
                    <div style={{ marginBottom: 16 }}>
                        <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                            Fertilizer Applications
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 10 }}>
                            <div className="form-group" style={{ margin: 0 }}>
                                <label className="form-label" style={{ fontSize: '0.68rem' }}>Day (1–150)</label>
                                <input
                                    className="form-input"
                                    type="number" min={1} max={150} placeholder="10"
                                    value={newFert.day}
                                    onChange={e => setNewFert(f => ({ ...f, day: e.target.value }))}
                                    style={{ width: 80 }}
                                />
                            </div>
                            <div className="form-group" style={{ margin: 0 }}>
                                <label className="form-label" style={{ fontSize: '0.68rem' }}>kg N/ha</label>
                                <input
                                    className="form-input"
                                    type="number" min={1} placeholder="80"
                                    value={newFert.amount}
                                    onChange={e => setNewFert(f => ({ ...f, amount: e.target.value }))}
                                    style={{ width: 90 }}
                                />
                            </div>
                            <div className="form-group" style={{ margin: 0 }}>
                                <label className="form-label" style={{ fontSize: '0.68rem' }}>Type</label>
                                <select
                                    className="form-select"
                                    value={newFert.fertType}
                                    onChange={e => setNewFert(f => ({ ...f, fertType: e.target.value }))}
                                    style={{ width: 110 }}
                                >
                                    <option value="urea">Urea</option>
                                    <option value="nitrate">Nitrate</option>
                                    <option value="ammonium">Ammonium</option>
                                </select>
                            </div>
                            <button
                                type="button"
                                className="btn btn-outline"
                                style={{ padding: '7px 14px', fontSize: '0.78rem', height: 36, alignSelf: 'flex-end' }}
                                onClick={addFertEvent}
                            >
                                + Add Fertilizer Application
                            </button>
                        </div>
                        {fertEvents.length > 0 && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                {fertEvents.map(e => (
                                    <div key={e.id} style={{
                                        display: 'inline-flex', alignItems: 'center', gap: 6,
                                        padding: '4px 10px', borderRadius: 999,
                                        background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.25)',
                                        fontSize: '0.78rem', color: 'var(--text-secondary)',
                                    }}>
                                        <span style={{ color: 'var(--green-400)', fontWeight: 600 }}>Day {e.day}</span>
                                        &mdash; {e.amount} kg N/ha ({e.fertType})
                                        <button
                                            type="button"
                                            onClick={() => removeFertEvent(e.id)}
                                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 2px', lineHeight: 1, fontSize: '0.85rem' }}
                                        >✕</button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Irrigation */}
                    <div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                            Irrigation Events
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 10 }}>
                            <div className="form-group" style={{ margin: 0 }}>
                                <label className="form-label" style={{ fontSize: '0.68rem' }}>Day (1–150)</label>
                                <input
                                    className="form-input"
                                    type="number" min={1} max={150} placeholder="15"
                                    value={newIrrig.day}
                                    onChange={e => setNewIrrig(f => ({ ...f, day: e.target.value }))}
                                    style={{ width: 80 }}
                                />
                            </div>
                            <div className="form-group" style={{ margin: 0 }}>
                                <label className="form-label" style={{ fontSize: '0.68rem' }}>Amount (mm)</label>
                                <input
                                    className="form-input"
                                    type="number" min={1} placeholder="25"
                                    value={newIrrig.amount}
                                    onChange={e => setNewIrrig(f => ({ ...f, amount: e.target.value }))}
                                    style={{ width: 90 }}
                                />
                            </div>
                            <button
                                type="button"
                                className="btn btn-outline"
                                style={{ padding: '7px 14px', fontSize: '0.78rem', height: 36, alignSelf: 'flex-end' }}
                                onClick={addIrrigEvent}
                            >
                                + Add Irrigation Event
                            </button>
                        </div>
                        {irrigEvents.length > 0 && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                {irrigEvents.map(e => (
                                    <div key={e.id} style={{
                                        display: 'inline-flex', alignItems: 'center', gap: 6,
                                        padding: '4px 10px', borderRadius: 999,
                                        background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.25)',
                                        fontSize: '0.78rem', color: 'var(--text-secondary)',
                                    }}>
                                        <span style={{ color: '#38bdf8', fontWeight: 600 }}>Day {e.day}</span>
                                        &mdash; {e.amount}mm
                                        <button
                                            type="button"
                                            onClick={() => removeIrrigEvent(e.id)}
                                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 2px', lineHeight: 1, fontSize: '0.85rem' }}
                                        >✕</button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
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
                <>
                {activeScenario && (
                    <div style={{ color: '#9ca3af', fontSize: 12, marginBottom: 8 }}>
                        Scenario: {activeScenario}
                    </div>
                )}

                {/* Scenario Comparison Panel — shown only when both scenarios have been run */}
                {scenario1Result && scenario2Result && (() => {
                    const pf_bu = kgHaToBuAcre(scenario1Result.final_yield_kg_ha || 0);
                    const wm_bu = kgHaToBuAcre(scenario2Result.final_yield_kg_ha || 0);
                    const gap_bu = wm_bu - pf_bu;
                    const commodityPrice = parseFloat(form.commodity_price_usd_bu) || 4.5;
                    const fieldAcres = parseFloat(form.field_acres) || 100;
                    const gap_dollar_acre = gap_bu * commodityPrice;
                    const gap_total = gap_dollar_acre * fieldAcres;
                    const barPct = wm_bu > 0 ? Math.min(100, Math.max(0, (pf_bu / wm_bu) * 100)) : 0;
                    return (
                        <div style={{
                            marginBottom: 20, borderRadius: 12, overflow: 'hidden',
                            border: '1px solid rgba(74,222,128,0.25)', background: 'var(--bg-card)',
                        }}>
                            {/* Header */}
                            <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', background: 'rgba(74,222,128,0.05)' }}>
                                <span style={{ fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--green-400)' }}>
                                    📊 Scenario Comparison
                                </span>
                            </div>
                            {/* Two columns */}
                            <div className="scenario-compare-cols" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--border)' }}>
                                <div style={{ padding: '16px 20px', borderRight: '1px solid var(--border)' }}>
                                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#b45309', marginBottom: 6 }}>🌽 Problem Field</div>
                                    <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#f59e0b', lineHeight: 1 }}>{fmtDec(pf_bu, 1)}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>bu/acre</div>
                                </div>
                                <div style={{ padding: '16px 20px' }}>
                                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#15803d', marginBottom: 6 }}>✅ Well-Managed</div>
                                    <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#4ade80', lineHeight: 1 }}>{fmtDec(wm_bu, 1)}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>bu/acre</div>
                                </div>
                            </div>
                            {/* Gap row */}
                            <div style={{ padding: '16px 20px' }}>
                                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f0fdf4', marginBottom: 12 }}>
                                    Yield Gap:&nbsp;
                                    <span style={{ color: '#fbbf24' }}>{fmtDec(gap_bu, 1)} bu/acre</span>
                                    &nbsp;=&nbsp;
                                    <span style={{ color: '#fbbf24' }}>${fmtDec(gap_dollar_acre, 0)}/acre</span>
                                    &nbsp;=&nbsp;
                                    <span style={{ color: '#fbbf24' }}>${Number(gap_total).toLocaleString('en-US', { maximumFractionDigits: 0 })} total</span>
                                </div>
                                {/* Progress bar */}
                                <div style={{ height: 12, borderRadius: 999, overflow: 'hidden', background: '#15803d', position: 'relative' }}>
                                    <div style={{
                                        position: 'absolute', left: 0, top: 0, bottom: 0,
                                        width: `${barPct}%`,
                                        background: '#b45309',
                                        borderRadius: '999px 0 0 999px',
                                        transition: 'width 0.5s ease',
                                    }} />
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                                    <span style={{ color: '#b45309' }}>Problem Field</span>
                                    <span style={{ color: '#15803d' }}>Well-Managed</span>
                                </div>
                            </div>
                        </div>
                    );
                })()}
                <div ref={reportRef} style={{ background: 'var(--bg-primary)', padding: '20px 0' }}>
                    <div className="pdf-only-title" style={{ display: 'none' }}>
                        <h2 style={{ margin: 0, color: 'var(--green-400)' }}>AgroVisus Platform</h2>
                        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Simulation Report: {templates.find(t => t.id === form.crop_template)?.name || form.crop_template}</p>
                        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Generated: {new Date().toLocaleDateString()}</p>
                    </div>

                    {/* KPI Cards */}
                    {(() => {
                        const dis = result.max_disease_severity ?? 0;
                        const diseaseColor = dis > 5 ? '#f87171' : dis >= 1 ? '#fbbf24' : '#4ade80';
                        const yieldBu = kgHaToBuAcre(result.final_yield_kg_ha || 0);
                        const highAlerts = groupedRules.filter(r => ['High','Critical'].includes(r.severity)).length;
                        const modAlerts  = groupedRules.filter(r => ['Moderate','Medium'].includes(r.severity)).length;
                        const grade = getFieldHealthGrade(result.final_yield_kg_ha, highAlerts, modAlerts);
                        const gradeStyle = GRADE_STYLE[grade];
                        return (
                            <div className="card-grid sim-kpi-grid mb-4" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
                                <div className="stat-tile" style={{ borderLeft: '3px solid #14b8a6' }}>
                                    <span className="stat-label">TOTAL BIOMASS (DM)</span>
                                    <span className="stat-value">{result.total_biomass_kg_ha?.toFixed(0)}</span>
                                    <span className="stat-sub">kg/ha · Total dry matter</span>
                                </div>
                                <div className="stat-tile" style={{ borderLeft: '3px solid #22c55e' }}>
                                    <span className="stat-label">FINAL YIELD</span>
                                    <span className="stat-value" style={{ fontSize: '1.6rem' }}>{fmtDec(yieldBu, 1)} bu/acre</span>
                                    <span className="stat-sub">{Number(result.final_yield_kg_ha).toLocaleString('en-US', { maximumFractionDigits: 0 })} kg/ha · Grain yield</span>
                                </div>
                                <div className="stat-tile" style={{ borderLeft: '3px solid #38bdf8' }}>
                                    <span className="stat-label">TOTAL IRRIGATION</span>
                                    <span className="stat-value">{result.total_irrigation_mm?.toFixed(0)}</span>
                                    <span className="stat-sub">mm · Applied water</span>
                                </div>
                                <div className="stat-tile" style={{ borderLeft: `3px solid ${diseaseColor}` }}>
                                    <span className="stat-label">MAX DISEASE</span>
                                    <span className="stat-value" style={{ color: diseaseColor }}>{dis.toFixed(1)}%</span>
                                    <span className="stat-sub">Peak severity</span>
                                </div>
                                <div className="stat-tile" style={{ borderLeft: `3px solid ${gradeStyle.color}` }}>
                                    <span className="stat-label">FIELD HEALTH</span>
                                    <span className="stat-value" style={{ fontSize: '2.4rem', color: gradeStyle.color }}>{grade}</span>
                                    <span className="stat-sub" style={{ color: gradeStyle.color }}>{gradeStyle.label}</span>
                                </div>
                            </div>
                        );
                    })()}

                    {/* Section divider */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, margin: '8px 0 20px' }}>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                        <span style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                            Field Performance
                        </span>
                        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
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
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={11} tickFormatter={fmtDate} interval={Math.max(0, Math.ceil((result.daily_data?.length || 1) / 8) - 1)} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Area type="monotone" dataKey="biomass_kg_ha" stroke="#22c55e" fill="url(#biomassGrad)" strokeWidth={2.5} dot={false} />
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
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={11} tickFormatter={fmtDate} interval={Math.max(0, Math.ceil((result.daily_data?.length || 1) / 8) - 1)} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} domain={[0, 1.2]} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Line type="monotone" dataKey="soil_moisture" stroke="#38bdf8" strokeWidth={2.5} dot={false} name="Soil Moisture" />
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
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={11} tickFormatter={fmtDate} interval={Math.max(0, Math.ceil((result.daily_data?.length || 1) / 8) - 1)} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} domain={[0, 1]} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)' }} />
                                        <ReferenceLine y={0.5} stroke="#6b7280" strokeDasharray="4 3" label={{ value: 'Stress threshold', position: 'insideTopRight', fontSize: 10, fill: '#6b7280' }} />
                                        <Line type="monotone" dataKey="water_stress" stroke="#f87171" strokeWidth={2.5} dot={false} name="Water Stress" />
                                        <Line type="monotone" dataKey="nitrogen_stress" stroke="#fbbf24" strokeWidth={3} dot={false} name="N Stress" />
                                        <Line type="monotone" dataKey="disease_severity" stroke="#c084fc" strokeWidth={2.5} dot={false} name="Disease %" />
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
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={11} tickFormatter={fmtDate} interval={Math.max(0, Math.ceil((result.daily_data?.length || 1) / 8) - 1)} />
                                        <YAxis stroke="var(--text-muted)" fontSize={11} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Area type="monotone" dataKey="avg_temp_c" stroke="#fb923c" fill="rgba(251,146,60,0.15)" strokeWidth={2.5} dot={false} name="Avg Temp °C" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>

                    {/* Weather Info Strip */}
                    {(() => {
                        const daily = result.daily_data || [];
                        const peakTemp = daily.length ? Math.max(...daily.map(d => d.avg_temp_c || 0)).toFixed(0) : '—';
                        const totalRain = daily.length ? daily.reduce((s, d) => s + (d.rainfall_mm || 0), 0).toFixed(0) : '—';
                        const startD = result.daily_data?.[0]?.date || form.start_date;
                        const endD   = result.daily_data?.[result.daily_data.length - 1]?.date || '';
                        const histDays = result.weather_source?.historical_days ?? daily.length;
                        return (
                            <div style={{ margin: '20px 0 4px', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                                <button
                                    onClick={() => setWeatherStripOpen(o => !o)}
                                    style={{
                                        width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                                        padding: '8px 14px', background: 'rgba(255,255,255,0.02)',
                                        border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8rem',
                                    }}
                                >
                                    <span style={{ fontSize: '0.75rem', transition: 'transform 0.2s', display: 'inline-block', transform: weatherStripOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
                                    <span style={{ fontWeight: 600 }}>Weather Data</span>
                                </button>
                                {weatherStripOpen && (
                                    <div style={{ padding: '10px 14px 12px', fontSize: '0.8rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border)', lineHeight: 1.8 }}>
                                        📍 {form.latitude.toFixed(1)}°N, {Math.abs(form.longitude).toFixed(1)}°W
                                        &nbsp;·&nbsp; {fmtDateFull(startD)}{endD ? ` – ${fmtDateFull(endD)}` : ''}
                                        &nbsp;·&nbsp; 🌦 {histDays} historical days (Open-Meteo ERA5-Land)
                                        &nbsp;·&nbsp; Peak temp: {peakTemp}°C
                                        &nbsp;·&nbsp; Total rain: {totalRain} mm
                                    </div>
                                )}
                            </div>
                        );
                    })()}

                    {/* Triggered Rules with ROI */}
                    {groupedRules.length > 0 && (() => {
                        const highAlerts = groupedRules.filter(r => ['High', 'Critical'].includes(r.severity));
                        const modAlerts  = groupedRules.filter(r => ['Moderate', 'Medium'].includes(r.severity));
                        const lowAlerts  = groupedRules.filter(r => r.severity === 'Low');
                        return (
                        <div className="card mt-6">
                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
                                <div>
                                    <h3 className="text-sm text-green" style={{ marginBottom: 8 }}>⚡ Advisory Alerts</h3>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                        {highAlerts.length > 0 && (
                                            <span style={{ fontSize: '0.8rem', color: '#f87171', fontWeight: 600 }}>
                                                ⚠ {highAlerts.length} HIGH alert{highAlerts.length > 1 ? 's' : ''} — requires immediate action
                                            </span>
                                        )}
                                        {modAlerts.length > 0 && (
                                            <span style={{ fontSize: '0.8rem', color: '#fbbf24', fontWeight: 500 }}>
                                                ℹ {modAlerts.length} MODERATE alert{modAlerts.length > 1 ? 's' : ''} — monitor closely
                                            </span>
                                        )}
                                        {lowAlerts.length > 0 && (
                                            <span style={{ fontSize: '0.8rem', color: '#4ade80', fontWeight: 500 }}>
                                                ✓ {lowAlerts.length} LOW alert{lowAlerts.length > 1 ? 's' : ''} — within acceptable range
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                    {form.field_acres} acres · ${form.treatment_cost_per_acre}/acre treatment cost
                                </span>
                            </div>
                            {/* Yield gap callout */}
                            {(() => {
                                const currentBu = kgHaToBuAcre(result.final_yield_kg_ha || 0);
                                const optimumBu = scenario2Result
                                    ? kgHaToBuAcre(scenario2Result.final_yield_kg_ha || 0)
                                    : 180;
                                const optimumLabel = scenario2Result
                                    ? `${fmtDec(optimumBu, 1)} bu/acre`
                                    : '~180 bu/acre (central Illinois avg)';
                                const gap = optimumBu - currentBu;
                                const commodityPrice = parseFloat(form.commodity_price_usd_bu) || 4.5;
                                const valueAtRisk = gap * commodityPrice;
                                return gap > 5 ? (
                                    <div style={{
                                        marginBottom: 16, padding: '14px 16px', borderRadius: 10,
                                        background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.3)',
                                    }}>
                                        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fbbf24', marginBottom: 10 }}>
                                            ⚠️ Estimated Season Impact
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 8, fontSize: '0.8rem' }}>
                                            {[
                                                { label: 'Projected yield', value: `${fmtDec(currentBu, 1)} bu/acre`, color: '#f87171' },
                                                { label: 'Optimum potential', value: optimumLabel, color: '#4ade80' },
                                                { label: 'Yield gap', value: `${fmtDec(gap, 0)} bu/acre`, color: '#fbbf24' },
                                                { label: 'Value at risk', value: `$${fmtDec(valueAtRisk, 0)}/acre`, color: '#fbbf24' },
                                            ].map(m => (
                                                <div key={m.label} style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)' }}>
                                                    <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 3 }}>{m.label}</div>
                                                    <div style={{ color: m.color, fontWeight: 700 }}>{m.value}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ) : null;
                            })()}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                {groupedRules.map((grp, i) => <RuleCard key={i} group={grp} fieldAcres={form.field_acres} treatmentCostPerAcre={form.treatment_cost_per_acre} />)}
                            </div>
                        </div>
                        );
                    })()}

                    {groupedRules.length === 0 && (() => {
                        const daily = result.daily_data || [];
                        const avgNStress = daily.length ? daily.reduce((s, d) => s + (d.nitrogen_stress ?? 1), 0) / daily.length : 1;
                        const avgFAWC   = daily.length ? daily.reduce((s, d) => s + (d.soil_moisture ?? 0.85), 0) / daily.length : 0.85;
                        const maxDis = result.max_disease_severity ?? 0;
                        const nLabel     = avgNStress > 0.8 ? 'Adequate' : avgNStress >= 0.5 ? 'Low' : 'Deficient';
                        const waterLabel = avgFAWC > 0.6 ? 'Sufficient' : avgFAWC >= 0.3 ? 'Moderate Stress' : 'Severe Stress';
                        const disLabel   = maxDis < 5 ? 'Low Risk' : maxDis < 20 ? 'Moderate' : 'High';
                        const statusColor = (s) => {
                            if (['Adequate','Sufficient','Low Risk'].includes(s)) return '#4ade80';
                            if (['Low','Moderate Stress','Moderate'].includes(s)) return '#fbbf24';
                            return '#f87171';
                        };
                        return (
                            <div className="card mt-6" style={{ padding: '28px 24px' }}>
                                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                                    <div style={{ fontSize: '1.5rem', marginBottom: 6 }}>✅</div>
                                    <div style={{ color: 'var(--green-400)', fontWeight: 700, fontSize: '1rem', marginBottom: 4 }}>Field is performing well</div>
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 16 }}>
                                    {[
                                        { label: 'N Status', status: nLabel },
                                        { label: 'Water', status: waterLabel },
                                        { label: 'Disease', status: disLabel },
                                    ].map(item => (
                                        <div key={item.label} style={{
                                            textAlign: 'center', padding: '14px 10px', borderRadius: 10,
                                            background: 'rgba(255,255,255,0.02)', border: `1px solid ${statusColor(item.status)}40`,
                                        }}>
                                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>{item.label}</div>
                                            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: statusColor(item.status), marginBottom: 4 }}>{item.status}</div>
                                            <div style={{ color: statusColor(item.status), fontSize: '1.1rem' }}>✓</div>
                                        </div>
                                    ))}
                                </div>
                                <div style={{ textAlign: 'center', fontSize: '0.83rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                    Conditions stayed within acceptable thresholds. Continue current management practices.
                                </div>
                            </div>
                        );
                    })()}

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
                </>
            )}
        </div>
    );
}

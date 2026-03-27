import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { exportElementToPDF } from '../utils/pdfExport';
import {
    Area, AreaChart, CartesianGrid, Line, LineChart,
    ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

// ── helpers ────────────────────────────────────────────────────────────────
function kgHaToBuAcre(v) { return ((v || 0) / 62.77).toFixed(1); }
function fmtDate(s) {
    if (!s) return '';
    const d = new Date(s + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
function fmtDateFull(s) {
    if (!s) return '—';
    const d = new Date(s + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
function getGrade(yieldKgHa, highAlerts, modAlerts) {
    const bu = (yieldKgHa || 0) / 62.77;
    if (bu < 80)  return { grade: 'F', color: '#f87171' };
    if (highAlerts >= 2 || bu < 110) return { grade: 'D', color: '#f87171' };
    if (highAlerts >= 1 || bu < 140) return { grade: 'C', color: '#fbbf24' };
    if (highAlerts === 0 && bu > 170 && modAlerts <= 1) return { grade: 'A', color: '#4ade80' };
    return { grade: 'B', color: '#4ade80' };
}
function severityColor(s) {
    if (['High','Critical'].includes(s)) return '#f87171';
    if (['Moderate','Medium'].includes(s)) return '#fbbf24';
    return '#4ade80';
}

// ── chart tooltip ──────────────────────────────────────────────────────────
const DarkTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
        <div style={{ background:'#141e17', border:'1px solid var(--border)',
            borderRadius:8, padding:'8px 12px', fontSize:12 }}>
            <div style={{ color:'var(--text-muted)', marginBottom:4 }}>{fmtDate(label)}</div>
            {payload.map(p => (
                <div key={p.dataKey} style={{ color: p.color, display:'flex', gap:8 }}>
                    <span>{p.name}:</span>
                    <span style={{ fontWeight:600 }}>{typeof p.value === 'number' ? p.value.toFixed(2) : p.value}</span>
                </div>
            ))}
        </div>
    );
};

// ── main ───────────────────────────────────────────────────────────────────
export default function Reports() {
    const reportRef = useRef(null);
    const [exporting, setExporting] = useState(false);
    const [exportError, setExportError] = useState(null);

    // Read from sessionStorage
    let result = null;
    let form   = null;
    try {
        const r = sessionStorage.getItem('agrovisus_sim_result');
        const f = sessionStorage.getItem('agrovisus_sim_form');
        if (r) result = JSON.parse(r);
        if (f) form   = JSON.parse(f);
    } catch { /* ignore */ }

    // Build grouped rules (same logic as Simulate.jsx)
    const groupedRules = [];
    if (result?.triggered_rules) {
        for (const day of result.triggered_rules) {
            for (const r of day.rules || []) {
                groupedRules.push({
                    id:         r.rule_id,
                    name:       r.name || r.rule_id,
                    severity:   r.severity,
                    alert_type: r.alert_type,
                    recommendation: r.recommendation,
                    roi:        r.roi,
                    daysActive: day.days_active || 1,
                });
            }
        }
    }

    const highAlerts = groupedRules.filter(r => ['High','Critical'].includes(r.severity)).length;
    const modAlerts  = groupedRules.filter(r => ['Moderate','Medium'].includes(r.severity)).length;
    const { grade, color: gradeColor } = getGrade(result?.final_yield_kg_ha, highAlerts, modAlerts);
    const daily = result?.daily_data || [];
    const startDate = daily[0]?.date || form?.start_date || '';
    const endDate   = daily[daily.length - 1]?.date || '';
    const cropName  = form?.crop_template
        ? form.crop_template.charAt(0).toUpperCase() + form.crop_template.slice(1)
        : 'Crop';

    async function handleExport() {
        setExporting(true);
        setExportError(null);
        const ok = await exportElementToPDF(
            reportRef.current,
            `agrovisus-report-${form?.crop_template || 'sim'}-${startDate || 'latest'}.pdf`
        );
        if (!ok) setExportError('PDF export failed. Try again.');
        setExporting(false);
    }

    // ── Empty state ────────────────────────────────────────────────────────
    if (!result) {
        return (
            <div>
                <div className="page-header">
                    <h2>📊 Reports</h2>
                    <p>Simulation reports appear here after you run a simulation.</p>
                </div>
                <div className="card" style={{ textAlign:'center', padding:'60px 24px' }}>
                    <div style={{ fontSize:'3rem', marginBottom:16 }}>📑</div>
                    <h3 style={{ color:'var(--text-secondary)', marginBottom:8 }}>No reports yet</h3>
                    <p className="text-sm" style={{ color:'var(--text-muted)', marginBottom:24 }}>
                        Run your first simulation to generate a field report.
                    </p>
                    <Link to="/simulate">
                        <button className="btn btn-primary">Go to Simulation →</button>
                    </Link>
                </div>
            </div>
        );
    }

    // ── Full report ────────────────────────────────────────────────────────
    return (
        <div>
            {/* Page header */}
            <div className="page-header" style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', flexWrap:'wrap', gap:12 }}>
                <div>
                    <h2>📊 Reports</h2>
                    <p>{cropName} · {fmtDateFull(startDate)} → {fmtDateFull(endDate)}</p>
                </div>
                <div style={{ display:'flex', gap:10, alignItems:'center' }}>
                    {exportError && (
                        <span style={{ fontSize:12, color:'var(--red-400)' }}>{exportError}</span>
                    )}
                    <button
                        className="btn btn-outline"
                        onClick={handleExport}
                        disabled={exporting}
                        style={{ display:'flex', alignItems:'center', gap:8 }}
                    >
                        {exporting ? '⏳ Generating…' : '⬇ Export PDF'}
                    </button>
                    <Link to="/simulate">
                        <button className="btn btn-primary">New Simulation →</button>
                    </Link>
                </div>
            </div>

            {/* Exportable content */}
            <div ref={reportRef}>

                {/* Report header block */}
                <div className="card" style={{ marginBottom:16 }}>
                    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:16 }}>
                        <div>
                            <div style={{ fontSize:11, letterSpacing:'1.5px', textTransform:'uppercase',
                                color:'var(--text-muted)', marginBottom:6 }}>
                                Field Simulation Report
                            </div>
                            <div style={{ fontSize:22, fontWeight:700, color:'var(--green-400)', marginBottom:4 }}>
                                AgroVisus Platform
                            </div>
                            <div style={{ fontSize:13, color:'var(--text-muted)' }}>
                                {cropName} · {form?.state_code || 'IL'} ·{' '}
                                {daily.length}-day simulation ·{' '}
                                {fmtDateFull(startDate)} → {fmtDateFull(endDate)}
                            </div>
                        </div>
                        {/* Field Health Grade */}
                        <div style={{ textAlign:'center' }}>
                            <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:4,
                                letterSpacing:'1px', textTransform:'uppercase' }}>Field Health</div>
                            <div style={{ width:64, height:64, borderRadius:12,
                                background:'var(--bg-secondary)', border:`2px solid ${gradeColor}`,
                                display:'flex', alignItems:'center', justifyContent:'center',
                                fontSize:32, fontWeight:700, color:gradeColor }}>
                                {grade}
                            </div>
                        </div>
                    </div>
                </div>

                {/* KPI cards */}
                <div className="card-grid card-grid-4" style={{ marginBottom:16 }}>
                    <div className="stat-tile">
                        <div className="stat-label">Final Yield</div>
                        <div className="stat-value" style={{ color:'var(--green-400)' }}>
                            {kgHaToBuAcre(result.final_yield_kg_ha)}
                        </div>
                        <div className="stat-sub">bu/acre · {Number(result.final_yield_kg_ha || 0).toLocaleString('en-US', { maximumFractionDigits:0 })} kg/ha</div>
                    </div>
                    <div className="stat-tile">
                        <div className="stat-label">Total Biomass</div>
                        <div className="stat-value">{Number(result.total_biomass_kg_ha || 0).toFixed(0)}</div>
                        <div className="stat-sub">kg/ha</div>
                    </div>
                    <div className="stat-tile">
                        <div className="stat-label">Peak Disease</div>
                        <div className="stat-value" style={{ color: result.max_disease_severity > 0.4 ? 'var(--red-400)' : 'var(--green-400)' }}>
                            {((result.max_disease_severity || 0) * 100).toFixed(0)}%
                        </div>
                        <div className="stat-sub">max severity</div>
                    </div>
                    <div className="stat-tile">
                        <div className="stat-label">Active Alerts</div>
                        <div className="stat-value" style={{ color: highAlerts > 0 ? 'var(--red-400)' : 'var(--green-400)' }}>
                            {groupedRules.length}
                        </div>
                        <div className="stat-sub">
                            {highAlerts > 0 ? `${highAlerts} high severity` : 'no high severity'}
                        </div>
                    </div>
                </div>

                {/* Charts row */}
                <div className="card-grid card-grid-2" style={{ marginBottom:16 }}>
                    {/* Biomass chart */}
                    <div className="card">
                        <h3 className="text-sm text-green" style={{ marginBottom:12 }}>
                            Biomass Accumulation (kg/ha)
                        </h3>
                        <ResponsiveContainer width="100%" height={160}>
                            <AreaChart data={daily}>
                                <defs>
                                    <linearGradient id="biomassGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#4ade80" stopOpacity={0.3}/>
                                        <stop offset="95%" stopColor="#4ade80" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={10}
                                    tickFormatter={fmtDate}
                                    interval={Math.max(0, Math.ceil(daily.length / 6) - 1)} />
                                <YAxis stroke="var(--text-muted)" fontSize={10} />
                                <Tooltip content={<DarkTooltip />} />
                                <Area type="monotone" dataKey="biomass_kg_ha"
                                    stroke="#4ade80" strokeWidth={2}
                                    fill="url(#biomassGrad)" name="Biomass" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Stress factors chart */}
                    <div className="card">
                        <h3 className="text-sm text-green" style={{ marginBottom:12 }}>
                            Stress Factors (0–1)
                        </h3>
                        <ResponsiveContainer width="100%" height={160}>
                            <LineChart data={daily}>
                                <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={10}
                                    tickFormatter={fmtDate}
                                    interval={Math.max(0, Math.ceil(daily.length / 6) - 1)} />
                                <YAxis stroke="var(--text-muted)" fontSize={10} domain={[0,1]} />
                                <Tooltip content={<DarkTooltip />} />
                                <Line type="monotone" dataKey="water_stress_factor"
                                    stroke="#38bdf8" strokeWidth={1.5} dot={false} name="Water stress" />
                                <Line type="monotone" dataKey="n_stress_factor"
                                    stroke="#fbbf24" strokeWidth={1.5} dot={false} name="N stress" />
                                <Line type="monotone" dataKey="disease_severity"
                                    stroke="#f87171" strokeWidth={1.5} dot={false} name="Disease" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Alerts table */}
                {groupedRules.length > 0 && (
                    <div className="card" style={{ marginBottom:16 }}>
                        <h3 className="text-sm text-green" style={{ marginBottom:16 }}>
                            ⚡ Advisory Alerts ({groupedRules.length})
                        </h3>
                        <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
                            {groupedRules.map((r, i) => (
                                <div key={i} style={{
                                    display:'flex', gap:14, padding:'12px 14px',
                                    borderRadius:8, border:'1px solid var(--border)',
                                    background:'var(--bg-secondary)',
                                }}>
                                    <div style={{
                                        width:8, height:8, borderRadius:'50%',
                                        background: severityColor(r.severity),
                                        flexShrink:0, marginTop:5,
                                    }} />
                                    <div style={{ flex:1, minWidth:0 }}>
                                        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                                            <span style={{ fontSize:13, fontWeight:600,
                                                color: severityColor(r.severity) }}>{r.name}</span>
                                            <span style={{ fontSize:10, padding:'1px 7px',
                                                borderRadius:4, fontWeight:600,
                                                background: `${severityColor(r.severity)}20`,
                                                color: severityColor(r.severity) }}>
                                                {r.severity}
                                            </span>
                                            <span style={{ fontSize:10, color:'var(--text-muted)',
                                                marginLeft:'auto' }}>
                                                {r.daysActive} day{r.daysActive !== 1 ? 's' : ''} active
                                            </span>
                                        </div>
                                        {r.recommendation && (
                                            <div style={{ fontSize:12, color:'var(--text-muted)',
                                                lineHeight:1.5 }}>
                                                {r.recommendation}
                                            </div>
                                        )}
                                        {r.roi && (
                                            <div style={{ display:'flex', gap:16, marginTop:8 }}>
                                                <span style={{ fontSize:11, color:'var(--red-400)' }}>
                                                    Revenue at risk: ${r.roi.revenue_at_risk_per_acre?.toFixed(0) ?? '—'}/acre
                                                </span>
                                                <span style={{ fontSize:11, color:'var(--green-400)' }}>
                                                    ROI: {r.roi.roi_mid?.toFixed(0) ?? '—'}% mid
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Footer watermark */}
                <div style={{ textAlign:'center', padding:'16px 0', borderTop:'1px solid var(--border)' }}>
                    <span style={{ fontSize:10, color:'var(--text-muted)', letterSpacing:'1px' }}>
                        AGROVISUS · FAO-56 · USDA-ARS · ICAR · Generated {new Date().toLocaleDateString('en-US', { month:'long', day:'numeric', year:'numeric' })}
                    </span>
                </div>

            </div>
        </div>
    );
}

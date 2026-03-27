import { useState } from 'react';
import {
    Area,
    AreaChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

// ── Synthetic 30-day data ────────────────────────────────────────────────────
const START = new Date('2025-05-01');
const chartData = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(START);
    d.setDate(d.getDate() + i);
    const label = `${d.getMonth() + 1}/${d.getDate()}`;
    return {
        label,
        disease:  Math.round(20 + 50 * Math.abs(Math.sin(i * 0.35 + 0.8)) + Math.random() * 8),
        nutrient: Math.round(15 + 20 * Math.abs(Math.sin(i * 0.22 + 1.2)) + Math.random() * 5),
        yield:    Math.round(85 + 10 * Math.abs(Math.sin(i * 0.18)) + Math.random() * 3),
    };
});

// Show every 4th label on X axis
const xTicks = chartData
    .filter((_, i) => i % 4 === 0)
    .map((d) => d.label);

// ── Stat cards ───────────────────────────────────────────────────────────────
const STAT_CARDS = [
    { title: 'Overall Field Health', value: '84%',      delta: '+2% this week', accent: 'var(--green-400)' },
    { title: 'Active Disease Risk',  value: 'MED',      delta: '2 alerts open',  accent: 'var(--amber-400)' },
    { title: 'Projected Yield',      value: '187 bu/ac', delta: 'Well-managed avg', accent: 'var(--green-400)' },
    { title: 'Sim Engine Tests',     value: '167',      delta: '✓ All passing',  accent: '#4A9DF5' },
];

// ── Alerts ───────────────────────────────────────────────────────────────────
const ALERTS = [
    {
        title: 'NCLB Detection — Corn NW',
        dot: 'var(--red-400)',
        bg: 'var(--red-glow)',
        border: 'rgba(248,113,113,.2)',
        body: 'Leaf wetness 8h+, temp 23°C avg. Apply fungicide.',
        meta: '2h ago · 87% confidence',
    },
    {
        title: 'N Deficiency — Wheat Field 3',
        dot: 'var(--amber-400)',
        bg: 'var(--amber-glow)',
        border: 'rgba(251,191,36,.2)',
        body: 'NNI below 0.80. Side-dress within 48h.',
        meta: '5h ago · 74% confidence',
    },
    {
        title: 'Gray Leaf Spot — Forecast',
        dot: 'var(--amber-400)',
        bg: 'var(--amber-glow)',
        border: 'rgba(251,191,36,.2)',
        body: 'Onset in 6–8 days. Monitor mid-canopy.',
        meta: '12h ago · 68% confidence',
    },
    {
        title: 'Soybean BNF Window',
        dot: 'var(--green-400)',
        bg: 'var(--green-glow)',
        border: 'rgba(74,222,128,.2)',
        body: 'Soil temp 22°C, moisture optimal.',
        meta: '1d ago · 91% confidence',
    },
];

// ── Simulation status rows ───────────────────────────────────────────────────
const SIM_ROWS = [
    { crop: 'Corn',    stage: 'V8', stageType: 'V', health: 79, gdd: 1248, risk: 'MED' },
    { crop: 'Wheat',   stage: 'R2', stageType: 'R', health: 64, gdd: 2104, risk: 'HIGH' },
    { crop: 'Soybean', stage: 'V5', stageType: 'V', health: 88, gdd:  784, risk: 'LOW' },
    { crop: 'Sorghum', stage: 'V4', stageType: 'V', health: 91, gdd:  612, risk: 'LOW' },
    { crop: 'Rice',    stage: 'R1', stageType: 'R', health: 72, gdd: 1560, risk: 'MED' },
];

// ── AI Advisory items ────────────────────────────────────────────────────────
const ADVISORY = [
    {
        label: 'Corn',      labelColor: 'var(--red-400)',   conf: 87,
        text: 'Apply 12 oz/ac fungicide within 48h. NCLB pressure elevated — leaf wetness threshold exceeded.',
    },
    {
        label: 'Wheat',     labelColor: 'var(--amber-400)', conf: 74,
        text: 'Side-dress 30 lb N/ac now. NNI at 0.76 is sub-optimal for current R2 stage demand.',
    },
    {
        label: 'Soybean',   labelColor: 'var(--green-400)', conf: 91,
        text: 'No action required. BNF running at 82% efficiency. Maintain current irrigation cadence.',
    },
    {
        label: 'Sorghum',   labelColor: 'var(--green-400)', conf: 88,
        text: 'Field health excellent. Consider delaying next irrigation 3 days — soil PAW at 74%.',
    },
];

// ── Sub-components ────────────────────────────────────────────────────────────
function StatCard({ title, value, delta, accent }) {
    return (
        <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            overflow: 'hidden',
        }}>
            <div style={{ height: 3, background: `linear-gradient(90deg, ${accent}55, ${accent})` }} />
            <div style={{ padding: '16px 18px' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                    {title}
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: accent, lineHeight: 1, marginBottom: 6 }}>
                    {value}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{delta}</div>
            </div>
        </div>
    );
}

function riskColor(risk) {
    return risk === 'HIGH' ? 'var(--red-400)'
         : risk === 'MED'  ? 'var(--amber-400)'
         :                   'var(--green-400)';
}
function riskBg(risk) {
    return risk === 'HIGH' ? 'var(--red-glow)'
         : risk === 'MED'  ? 'var(--amber-glow)'
         :                   'var(--green-glow)';
}

function HealthBar({ pct }) {
    const color = pct >= 80 ? 'var(--green-400)' : pct >= 60 ? 'var(--amber-400)' : 'var(--red-400)';
    return (
        <div style={{ width: 80, height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
        </div>
    );
}

const TOOLTIP_STYLE = {
    backgroundColor: '#141e17',
    border: '1px solid var(--border)',
    borderRadius: 8,
    fontSize: 12,
};

export default function Dashboard() {
    const [activeTab, setActiveTab] = useState('disease');

    const tabDataKey = activeTab;
    const tabColor   = activeTab === 'disease'  ? 'var(--red-400)'
                     : activeTab === 'nutrient' ? 'var(--amber-400)'
                     :                            'var(--green-400)';

    return (
        <>
            <style>{`
                @keyframes dash-pulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50%       { opacity: 0.4; transform: scale(0.85); }
                }
            `}</style>

            <div style={{ padding: '24px 32px' }}>

                {/* ── Page header ─────────────────────────────────────── */}
                <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
                            Field Operations Dashboard
                        </h2>
                        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>
                            Live overview across all active simulations
                        </p>
                    </div>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 7,
                        background: 'var(--green-glow)', border: '1px solid rgba(74,222,128,.25)',
                        borderRadius: 20, padding: '5px 13px',
                    }}>
                        <span style={{
                            width: 8, height: 8, borderRadius: '50%',
                            background: 'var(--green-400)',
                            animation: 'dash-pulse 1.8s ease-in-out infinite',
                            display: 'inline-block',
                        }} />
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--green-400)' }}>Engine Live</span>
                    </div>
                </div>

                {/* ── Stat cards ──────────────────────────────────────── */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20 }}>
                    {STAT_CARDS.map((c) => <StatCard key={c.title} {...c} />)}
                </div>

                {/* ── Mid row ─────────────────────────────────────────── */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, marginBottom: 20 }}>

                    {/* Risk Timeline */}
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                                Risk Timeline — 30 Day Forecast
                            </span>
                            <a href="#" style={{ fontSize: 12, color: 'var(--green-400)', textDecoration: 'none' }}>Export →</a>
                        </div>

                        {/* Tabs */}
                        <div style={{ display: 'flex', gap: 8, padding: '12px 18px 0' }}>
                            {[
                                { key: 'disease',  label: 'Disease Risk' },
                                { key: 'nutrient', label: 'Nutrient Stress' },
                                { key: 'yield',    label: 'Yield Index' },
                            ].map(({ key, label }) => (
                                <button
                                    key={key}
                                    onClick={() => setActiveTab(key)}
                                    style={{
                                        padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 6,
                                        cursor: 'pointer',
                                        background:   activeTab === key ? 'var(--green-glow)' : 'transparent',
                                        border:       activeTab === key ? '1px solid rgba(74,222,128,.2)' : '1px solid transparent',
                                        color:        activeTab === key ? 'var(--green-400)' : 'var(--text-muted)',
                                    }}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>

                        <div style={{ padding: '8px 18px 16px' }}>
                            <ResponsiveContainer width="100%" height={200}>
                                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%"  stopColor={tabColor} stopOpacity={0.25} />
                                            <stop offset="95%" stopColor={tabColor} stopOpacity={0.02} />
                                        </linearGradient>
                                    </defs>
                                    <XAxis
                                        dataKey="label"
                                        ticks={xTicks}
                                        stroke="var(--text-muted)"
                                        tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                                        axisLine={false}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        stroke="transparent"
                                        tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                                        axisLine={false}
                                        tickLine={false}
                                    />
                                    <Tooltip
                                        contentStyle={TOOLTIP_STYLE}
                                        labelStyle={{ color: 'var(--text-muted)', fontSize: 11 }}
                                        itemStyle={{ color: tabColor }}
                                    />
                                    <Area
                                        key={tabDataKey}
                                        type="monotone"
                                        dataKey={tabDataKey}
                                        stroke={tabColor}
                                        strokeWidth={2}
                                        fill="url(#areaGrad)"
                                        dot={false}
                                        isAnimationActive
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Active Alerts */}
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Active Alerts</span>
                            <a href="#" style={{ fontSize: 12, color: 'var(--green-400)', textDecoration: 'none' }}>View All</a>
                        </div>
                        <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {ALERTS.map((a) => (
                                <div
                                    key={a.title}
                                    style={{
                                        background: a.bg,
                                        border: `1px solid ${a.border}`,
                                        borderRadius: 8,
                                        padding: '10px 12px',
                                        display: 'flex',
                                        gap: 10,
                                        alignItems: 'flex-start',
                                    }}
                                >
                                    <span style={{
                                        width: 8, height: 8, borderRadius: '50%',
                                        background: a.dot, flexShrink: 0, marginTop: 4,
                                    }} />
                                    <div>
                                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                                            {a.title}
                                        </div>
                                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 3 }}>
                                            {a.body}
                                        </div>
                                        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{a.meta}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* ── Bottom row ──────────────────────────────────────── */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

                    {/* Crop Simulation Status */}
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                                Crop Simulation Status
                            </span>
                        </div>
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                        {['Crop', 'Stage', 'Health', 'GDD', 'Risk'].map((h) => (
                                            <th key={h} style={{
                                                padding: '8px 16px', textAlign: 'left',
                                                color: 'var(--text-muted)', fontWeight: 500,
                                                fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em',
                                            }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {SIM_ROWS.map((row, i) => (
                                        <tr
                                            key={row.crop}
                                            style={{
                                                borderBottom: i < SIM_ROWS.length - 1 ? '1px solid var(--border-light, var(--border))' : 'none',
                                            }}
                                        >
                                            <td style={{ padding: '10px 16px', color: 'var(--text-primary)', fontWeight: 500 }}>
                                                {row.crop}
                                            </td>
                                            <td style={{ padding: '10px 16px' }}>
                                                <span style={{
                                                    fontFamily: 'monospace', fontSize: 11, fontWeight: 600,
                                                    padding: '2px 7px', borderRadius: 4,
                                                    background: row.stageType === 'V' ? 'rgba(74,222,128,.12)' : 'rgba(74,158,245,.12)',
                                                    color:      row.stageType === 'V' ? 'var(--green-400)' : '#4A9DF5',
                                                    border: `1px solid ${row.stageType === 'V' ? 'rgba(74,222,128,.25)' : 'rgba(74,158,245,.25)'}`,
                                                }}>
                                                    {row.stage}
                                                </span>
                                            </td>
                                            <td style={{ padding: '10px 16px' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                    <HealthBar pct={row.health} />
                                                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{row.health}%</span>
                                                </div>
                                            </td>
                                            <td style={{ padding: '10px 16px', color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                                                {row.gdd.toLocaleString()}
                                            </td>
                                            <td style={{ padding: '10px 16px' }}>
                                                <span style={{
                                                    fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
                                                    background: riskBg(row.risk),
                                                    color: riskColor(row.risk),
                                                    border: `1px solid ${riskColor(row.risk)}44`,
                                                    letterSpacing: '0.04em',
                                                }}>
                                                    {row.risk}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* AI Advisory Feed */}
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>AI Advisory Feed</span>
                            <a href="#" style={{ fontSize: 12, color: 'var(--green-400)', textDecoration: 'none' }}>Regenerate</a>
                        </div>
                        <div style={{ padding: '10px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                            {ADVISORY.map((item) => (
                                <div key={item.label}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
                                        <span style={{ fontSize: 12, fontWeight: 600, color: item.labelColor }}>
                                            {item.label}
                                        </span>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <div style={{ width: 50, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                                                <div style={{ width: `${item.conf}%`, height: '100%', background: item.labelColor, borderRadius: 2 }} />
                                            </div>
                                            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{item.conf}%</span>
                                        </div>
                                    </div>
                                    <p style={{
                                        margin: '0 0 5px', fontSize: 12,
                                        color: 'var(--text-muted)', lineHeight: 1.5,
                                        display: '-webkit-box', WebkitLineClamp: 2,
                                        WebkitBoxOrient: 'vertical', overflow: 'hidden',
                                    }}>
                                        {item.text}
                                    </p>
                                    <a href="#" style={{ fontSize: 11, color: 'var(--green-400)', textDecoration: 'none' }}>
                                        View Full Advisory →
                                    </a>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

            </div>
        </>
    );
}

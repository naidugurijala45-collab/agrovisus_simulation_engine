import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

/* ── Animated Counter ──────────────────────────────────────────────────── */
function AnimatedCounter({ target, suffix = '', duration = 2000, prefix = '' }) {
    const [count, setCount] = useState(0);
    const ref = useRef(null);
    const started = useRef(false);

    useEffect(() => {
        const observer = new IntersectionObserver(([entry]) => {
            if (entry.isIntersecting && !started.current) {
                started.current = true;
                const startTime = performance.now();
                const isFloat = String(target).includes('.');
                const targetNum = parseFloat(target);
                const step = (now) => {
                    const elapsed = now - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    const eased = 1 - Math.pow(1 - progress, 4);
                    const val = eased * targetNum;
                    setCount(isFloat ? parseFloat(val.toFixed(1)) : Math.floor(val));
                    if (progress < 1) requestAnimationFrame(step);
                    else setCount(targetNum);
                };
                requestAnimationFrame(step);
            }
        }, { threshold: 0.3 });
        if (ref.current) observer.observe(ref.current);
        return () => observer.disconnect();
    }, [target, duration]);

    return <span ref={ref}>{prefix}{count}{suffix}</span>;
}

/* ── Particle Grid Background ─────────────────────────────────────────── */
function ParticleField() {
    const dots = Array.from({ length: 80 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.random() * 2 + 1,
        delay: Math.random() * 6,
        duration: Math.random() * 4 + 4,
    }));
    return (
        <div className="particle-field" aria-hidden>
            {dots.map((d) => (
                <div key={d.id} className="particle-dot" style={{
                    left: `${d.x}%`, top: `${d.y}%`,
                    width: d.size, height: d.size,
                    animationDelay: `${d.delay}s`,
                    animationDuration: `${d.duration}s`,
                }} />
            ))}
        </div>
    );
}

/* ── Floating Data Card ───────────────────────────────────────────────── */
function FloatingDataCard() {
    const bars = [45, 70, 55, 90, 65, 80, 75, 95];
    return (
        <div className="floating-card hero-data-card">
            <div className="fdc-header">
                <span className="fdc-dot green" />
                <span className="fdc-title">Live Simulation</span>
                <span className="badge badge-green" style={{ marginLeft: 'auto' }}>RUNNING</span>
            </div>
            <div className="fdc-chart">
                {bars.map((h, i) => (
                    <div key={i} className="fdc-bar-wrap">
                        <div className="fdc-bar" style={{
                            height: `${h}%`,
                            animationDelay: `${i * 0.15}s`,
                        }} />
                    </div>
                ))}
            </div>
            <div className="fdc-stats">
                <div><div className="fdc-stat-val text-green">8,420</div><div className="fdc-stat-lbl">kg/ha</div></div>
                <div><div className="fdc-stat-val" style={{ color: '#38bdf8' }}>72%</div><div className="fdc-stat-lbl">Water Eff.</div></div>
                <div><div className="fdc-stat-val" style={{ color: '#c084fc' }}>Day 67</div><div className="fdc-stat-lbl">Progress</div></div>
            </div>
        </div>
    );
}

/* ── DNA Helix Decoration ─────────────────────────────────────────────── */
function HelixDecoration() {
    const nodes = Array.from({ length: 12 }, (_, i) => i);
    return (
        <div className="helix-wrap" aria-hidden>
            {nodes.map((i) => (
                <div key={i} className="helix-row" style={{ animationDelay: `${i * 0.15}s` }}>
                    <div className="helix-node left" style={{ animationDelay: `${i * 0.15}s` }} />
                    <div className="helix-line" />
                    <div className="helix-node right" style={{ animationDelay: `${i * 0.15 + 0.5}s` }} />
                </div>
            ))}
        </div>
    );
}

/* ── Main Landing ─────────────────────────────────────────────────────── */
export default function Landing() {
    const navigate = useNavigate();
    const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

    useEffect(() => {
        const handler = (e) => setMousePos({ x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight });
        window.addEventListener('mousemove', handler);
        return () => window.removeEventListener('mousemove', handler);
    }, []);

    const parallaxX = (mousePos.x - 0.5) * 20;
    const parallaxY = (mousePos.y - 0.5) * 20;

    return (
        <div className="landing-root">

            {/* ── HERO ──────────────────────────────────────────────────────── */}
            <section className="lp-hero">
                <ParticleField />
                {/* Radial glow that follows mouse */}
                <div className="cursor-glow" style={{
                    left: `${mousePos.x * 100}%`,
                    top: `${mousePos.y * 100}%`,
                }} />

                <div className="lp-hero-grid">
                    {/* Left: Text */}
                    <div className="lp-hero-text">
                        <div className="lp-eyebrow">
                            <span className="eyebrow-dot" />
                            <span>AI-Powered Precision Agriculture</span>
                        </div>

                        <h1 className="lp-h1">
                            <span className="lp-h1-line">The Future of</span>
                            <span className="lp-h1-line gradient-text">Crop Intelligence</span>
                            <span className="lp-h1-line">Starts Here.</span>
                        </h1>

                        <p className="lp-subtext">
                            AgroVisus fuses physics-based simulation, reinforcement learning, and
                            AI diagnostics into one platform — telling farmers exactly when and
                            how much to irrigate, fertilise, and act.
                        </p>

                        <div className="lp-cta-row">
                            <button className="btn-hero-primary" onClick={() => navigate('/simulate')}>
                                <span className="btn-hero-glow" />
                                <span className="btn-hero-text">🌱 Run Simulation</span>
                            </button>
                            <button className="btn-hero-secondary" onClick={() => navigate('/disease')}>
                                <span>🦠 Diagnose a Crop</span>
                            </button>
                        </div>

                        <div className="lp-trust-row">
                            {['Physics-Based Engine', 'PPO RL Agent', 'Real Weather Data'].map((t) => (
                                <div key={t} className="lp-trust-pill">
                                    <span className="trust-check">✓</span> {t}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Right: Floating visual */}
                    <div className="lp-hero-visual" style={{
                        transform: `translate(${parallaxX}px, ${parallaxY}px)`,
                    }}>
                        <div className="hero-visual-glow" />
                        <FloatingDataCard />
                        <HelixDecoration />

                        {/* Orbiting badges */}
                        <div className="orbit-badge" style={{ top: '8%', right: '10%', animationDelay: '0s' }}>
                            <span>🛰️ Satellite</span>
                        </div>
                        <div className="orbit-badge" style={{ bottom: '20%', left: '-5%', animationDelay: '1.2s' }}>
                            <span>🤖 PPO Agent</span>
                        </div>
                        <div className="orbit-badge" style={{ top: '55%', right: '-8%', animationDelay: '0.6s' }}>
                            <span>⚡ 200k Steps</span>
                        </div>
                    </div>
                </div>

                {/* Scroll cue */}
                <div className="scroll-cue">
                    <div className="scroll-arrow" />
                </div>
            </section>

            {/* ── STATS BAND ────────────────────────────────────────────────── */}
            <section className="lp-stats-band">
                <div className="stats-band-inner">
                    {[
                        { val: 30, suffix: '%', label: 'Water Saved', color: '#38bdf8', icon: '💧' },
                        { val: 15, suffix: '%', label: 'Yield Gained', color: '#22c55e', icon: '🌾' },
                        { val: 18, suffix: '%', label: 'N-Waste Cut', color: '#c084fc', icon: '🧬' },
                        { val: 200, suffix: 'k', label: 'Training Steps', color: '#fbbf24', icon: '🤖' },
                    ].map((s) => (
                        <div key={s.label} className="stat-band-card">
                            <div className="sbc-icon">{s.icon}</div>
                            <div className="sbc-val" style={{ color: s.color }}>
                                <AnimatedCounter target={s.val} suffix={s.suffix} />
                            </div>
                            <div className="sbc-label">{s.label}</div>
                            <div className="sbc-glow" style={{ background: s.color }} />
                        </div>
                    ))}
                </div>
            </section>

            {/* ── FEATURES ──────────────────────────────────────────────────── */}
            <section className="lp-features">
                <div className="lp-section-header">
                    <span className="section-chip">Core Capabilities</span>
                    <h2 className="lp-section-title">Built for the <span className="gradient-text">precision farmer</span></h2>
                    <p className="lp-section-sub">Four integrated modules that work together to maximise yield and minimise waste.</p>
                </div>

                <div className="features-grid">
                    {[
                        {
                            icon: '🌱', color: '#22c55e', glow: 'rgba(34,197,94,0.15)',
                            title: 'Crop Simulation Engine',
                            desc: 'Physics-based simulation with GDD accumulation, water balance, nutrient cycling, disease pressure, and daily stage tracking.',
                            tags: ['Biomass', 'Soil Water', 'Disease'],
                        },
                        {
                            icon: '🤖', color: '#a78bfa', glow: 'rgba(167,139,250,0.15)',
                            title: 'Reinforcement Learning Agent',
                            desc: 'PPO v3 agent trained for 200,000 timesteps learns optimal irrigation and fertilization schedules across randomized growing seasons.',
                            tags: ['PPO', 'Stable-Baselines3', 'Reward Shaping'],
                        },
                        {
                            icon: '🦠', color: '#f87171', glow: 'rgba(248,113,113,0.15)',
                            title: 'AI Disease Diagnostics',
                            desc: 'Upload a leaf photo for instant AI-powered diagnosis with confidence scores, severity classification, and treatment recommendations.',
                            tags: ['Image Upload', 'CNN Ready', 'Actionable Advice'],
                        },
                        {
                            icon: '📊', color: '#fbbf24', glow: 'rgba(251,191,36,0.15)',
                            title: 'Smart Reporting & Export',
                            desc: 'Multi-run report history with filterable KPIs, interactive time-series charts, triggered advisory alerts, and CSV/PDF export.',
                            tags: ['CSV Export', 'Run History', 'AI vs Random'],
                        },
                    ].map((f) => (
                        <div key={f.title} className="feature-panel" style={{ '--accent': f.color, '--glow': f.glow }}>
                            <div className="fp-icon-wrap" style={{ background: f.glow }}>
                                <span className="fp-icon">{f.icon}</span>
                            </div>
                            <h3 className="fp-title">{f.title}</h3>
                            <p className="fp-desc">{f.desc}</p>
                            <div className="fp-tags">
                                {f.tags.map((t) => (
                                    <span key={t} className="fp-tag" style={{ borderColor: f.color, color: f.color }}>{t}</span>
                                ))}
                            </div>
                            <div className="fp-glow-corner" style={{ background: f.glow }} />
                        </div>
                    ))}
                </div>
            </section>

            {/* ── HOW IT WORKS ──────────────────────────────────────────────── */}
            <section className="lp-how">
                <div className="lp-section-header">
                    <span className="section-chip">Workflow</span>
                    <h2 className="lp-section-title">From seed to <span className="gradient-text">harvest insight</span></h2>
                </div>
                <div className="how-steps">
                    {[
                        { num: '01', icon: '⚙️', title: 'Configure', desc: 'Choose your crop, field location, soil type, and season length.' },
                        { num: '02', icon: '🔬', title: 'Simulate', desc: 'Run a full-season growth model using live weather and soil data.' },
                        { num: '03', icon: '🤖', title: 'Optimize', desc: 'AI finds the irrigation and fertilization plan that maximizes your yield.' },
                        { num: '04', icon: '📈', title: 'Act', desc: 'Receive day-by-day field recommendations you can put to work immediately.' },
                    ].map((s, i) => (
                        <div key={s.num} className="how-step">
                            <div className="hs-num">{s.num}</div>
                            <div className="hs-icon">{s.icon}</div>
                            <h4 className="hs-title">{s.title}</h4>
                            <p className="hs-desc">{s.desc}</p>
                            {i < 3 && <div className="hs-connector" />}
                        </div>
                    ))}
                </div>
            </section>

            {/* ── CTA BANNER ────────────────────────────────────────────────── */}
            <section className="lp-cta-banner">
                <div className="cta-banner-glow" />
                <div className="cta-banner-content">
                    <h2 className="cta-banner-title">Ready to grow smarter?</h2>
                    <p className="cta-banner-sub">Launch a simulation in under 30 seconds. No setup required.</p>
                    <button className="btn-hero-primary" onClick={() => navigate('/simulate')} style={{ margin: '0 auto' }}>
                        <span className="btn-hero-glow" />
                        <span className="btn-hero-text">🚀 Start Simulation Now</span>
                    </button>
                </div>
                {/* Decorative field rows */}
                <div className="field-rows" aria-hidden>
                    {Array.from({ length: 8 }).map((_, i) => (
                        <div key={i} className="field-row" style={{ animationDelay: `${i * 0.2}s` }} />
                    ))}
                </div>
            </section>

        </div>
    );
}

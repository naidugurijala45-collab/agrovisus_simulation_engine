import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

// ─── Data ─────────────────────────────────────────────────────────────────────
const CROPS = [
  { name: "Corn",    icon: "🌽", acres: "91.5M", rank: "#1", color: "#f59e0b" },
  { name: "Soybean", icon: "🫘", acres: "86.1M", rank: "#2", color: "#84cc16" },
  { name: "Wheat",   icon: "🌾", acres: "33.8M", rank: "#3", color: "#d97706" },
  { name: "Rice",    icon: "🌿", acres: "2.87M", rank: "#6", color: "#34d399" },
  { name: "Sorghum", icon: "🌱", acres: "5.5M",  rank: "#7", color: "#a3e635" },
];

const STATS = [
  {
    target: 11316, unit: "kg/ha",
    label: "Well-managed corn yield",
    sub: "vs 5,700 kg/ha problem field (91 bu/acre)",
    fmt: (n) => n >= 1000 ? `${Math.floor(n / 1000)},${String(n % 1000).padStart(3, "0")}` : String(n),
  },
  {
    target: 89, unit: "bu/acre",
    label: "Yield gap: problem vs well-managed",
    sub: "= $400/acre at $4.50/bu",
    fmt: (n) => String(n),
  },
  {
    target: 167, unit: "tests",
    label: "All passing, zero regressions",
    sub: "DSSAT · FAO-56 · USDA-ARS",
    fmt: (n) => String(n),
  },
  {
    target: 4, unit: "regions",
    label: "US Corn Belt coverage",
    sub: "OH · IN · IL · IA · KS · GA",
    fmt: (n) => String(n),
  },
];

const HOW_STEPS = [
  {
    num: "01",
    title: "Drop your pin",
    desc: "Search your field address. We resolve your region, soil defaults, and climate profile automatically.",
  },
  {
    num: "02",
    title: "Run the simulation",
    desc: "120-day daily engine pulls real historical weather for your coordinates, then tracks GDD, water balance, disease pressure, and nitrogen stress — day by day.",
  },
  {
    num: "03",
    title: "Get your diagnosis",
    desc: "Every triggered alert includes revenue at risk, yield loss projection, and treatment ROI.",
  },
];

const FEATURES = [
  {
    icon: "🦠", color: "#f87171",
    title: "Disease Detection",
    desc: "3 corn diseases running in parallel. NCLB, Gray Leaf Spot, Common Rust — each with humidity, temperature and leaf wetness thresholds.",
    tags: ["NCLB", "Gray Leaf Spot", "Common Rust"],
  },
  {
    icon: "💰", color: "#fbbf24",
    title: "ROI Calculator",
    desc: "Every alert shows revenue at risk, yield loss in bu/acre, and low/medium/high treatment ROI scenarios.",
    tags: ["Revenue at Risk", "Yield Loss", "Treatment ROI"],
  },
  {
    icon: "🗺️", color: "#38bdf8",
    title: "Regional Intelligence",
    desc: "4 US regions with disease multipliers. Ohio corn and Georgia corn get different risk profiles automatically.",
    tags: ["OH · IN · IL · IA", "Disease Multipliers", "Auto-resolved"],
  },
  {
    icon: "🌱", color: "#4ade80",
    title: "5-Crop Engine",
    desc: "Corn, soybean, wheat, rice, sorghum — all with FAO-56 and DSSAT v4.8 validated parameters.",
    tags: ["FAO-56", "DSSAT v4.8", "USDA-ARS"],
  },
];

// ─── Shared tokens ────────────────────────────────────────────────────────────
const G = "#4ade80";
const BG = "#080f09";
const MONO = "'DM Mono', monospace";
const SANS = "'DM Sans', sans-serif";
const BEBAS = "'Bebas Neue', sans-serif";

// ─── Hooks ────────────────────────────────────────────────────────────────────
function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setInView(true); },
      { threshold }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, inView];
}

// ─── Animated counter ─────────────────────────────────────────────────────────
function AnimCounter({ target, fmt, triggered }) {
  const [val, setVal] = useState(0);
  const started = useRef(false);
  useEffect(() => {
    if (!triggered || started.current) return;
    started.current = true;
    const DURATION = 1200;
    const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min((now - t0) / DURATION, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(Math.round(eased * target));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [triggered, target]);
  return <>{fmt(val)}</>;
}

// ─── CTAButton — reused in hero + footer ──────────────────────────────────────
function CTAButton({ style }) {
  const [hov, setHov] = useState(false);
  return (
    <Link
      to="/simulate"
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: "10px",
        background: G, color: BG,
        fontFamily: SANS, fontWeight: 700, fontSize: "15px",
        padding: "16px 36px", borderRadius: "2px",
        textDecoration: "none", letterSpacing: "0.01em",
        transform: hov ? "translateY(-2px)" : "translateY(0)",
        boxShadow: hov ? "0 8px 32px rgba(74,222,128,0.35)" : "0 0 0 rgba(74,222,128,0)",
        transition: "transform 0.2s ease, box-shadow 0.2s ease",
        ...style,
      }}
    >
      Run a Simulation <span style={{ fontSize: "18px", lineHeight: 1 }}>→</span>
    </Link>
  );
}

// ─── Section label ────────────────────────────────────────────────────────────
function SectionLabel({ label, refProp, inView }) {
  return (
    <div ref={refProp} style={{
      opacity: inView ? 1 : 0,
      transform: inView ? "translateY(0)" : "translateY(20px)",
      transition: "all 0.6s ease",
      display: "flex", alignItems: "center", gap: "16px", marginBottom: "48px",
    }}>
      <span style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(74,222,128,0.55)", letterSpacing: "0.2em", whiteSpace: "nowrap" }}>
        {label}
      </span>
      <div style={{ flex: 1, height: "1px", background: "rgba(74,222,128,0.1)" }} />
    </div>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ stat, delay }) {
  const [ref, inView] = useInView();
  return (
    <div ref={ref} style={{
      opacity: inView ? 1 : 0,
      transform: inView ? "translateY(0)" : "translateY(28px)",
      transition: `opacity 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms, transform 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms`,
      background: "rgba(255,255,255,0.02)",
      border: "1px solid rgba(74,222,128,0.1)",
      borderTop: "2px solid rgba(74,222,128,0.4)",
      borderRadius: "2px", padding: "32px 28px",
      position: "relative", overflow: "hidden",
    }}>
      {/* top shimmer line */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "1px",
        background: "linear-gradient(90deg, transparent, rgba(74,222,128,0.6), transparent)",
      }} />
      <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "8px" }}>
        <span style={{ fontFamily: BEBAS, fontSize: "52px", color: G, lineHeight: 1, letterSpacing: "0.02em" }}>
          <AnimCounter target={stat.target} fmt={stat.fmt} triggered={inView} />
        </span>
        <span style={{ fontFamily: BEBAS, fontSize: "22px", color: "rgba(74,222,128,0.5)", letterSpacing: "0.05em" }}>
          {stat.unit}
        </span>
      </div>
      <div style={{ fontFamily: SANS, fontSize: "13px", color: "rgba(255,255,255,0.7)", marginBottom: "4px", fontWeight: 500 }}>
        {stat.label}
      </div>
      <div style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(74,222,128,0.4)", letterSpacing: "0.08em" }}>
        {stat.sub}
      </div>
    </div>
  );
}

// ─── How-it-works card ────────────────────────────────────────────────────────
function HowCard({ step, delay, parentInView }) {
  return (
    <div style={{
      opacity: parentInView ? 1 : 0,
      transform: parentInView ? "translateX(0)" : "translateX(-24px)",
      transition: `opacity 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms, transform 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms`,
      display: "flex", alignItems: "stretch",
      background: "rgba(255,255,255,0.02)",
      border: "1px solid rgba(255,255,255,0.06)",
      borderRadius: "4px", overflow: "hidden",
    }}>
      {/* Big number */}
      <div style={{
        padding: "32px 36px",
        borderRight: "1px solid rgba(74,222,128,0.1)",
        display: "flex", alignItems: "center", justifyContent: "center",
        minWidth: "120px",
        background: "rgba(74,222,128,0.02)",
      }}>
        <span style={{ fontFamily: BEBAS, fontSize: "64px", color: "rgba(74,222,128,0.2)", lineHeight: 1, letterSpacing: "0.02em" }}>
          {step.num}
        </span>
      </div>
      {/* Green accent bar */}
      <div style={{ width: "3px", background: `linear-gradient(180deg, ${G}, rgba(74,222,128,0.1))`, flexShrink: 0 }} />
      {/* Content */}
      <div style={{ padding: "32px 36px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ fontFamily: BEBAS, fontSize: "22px", color: "rgba(255,255,255,0.9)", letterSpacing: "0.06em", marginBottom: "10px" }}>
          {step.title}
        </div>
        <p style={{ fontFamily: SANS, fontSize: "14px", color: "rgba(255,255,255,0.45)", lineHeight: 1.75, maxWidth: "560px" }}>
          {step.desc}
        </p>
      </div>
    </div>
  );
}

// ─── Feature card ─────────────────────────────────────────────────────────────
function FeatureCard({ feat, delay }) {
  const [ref, inView] = useInView();
  const [hov, setHov] = useState(false);
  return (
    <div
      ref={ref}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(28px)",
        transition: `opacity 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms, transform 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms, background 0.2s, border-color 0.2s`,
        background: hov ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.015)",
        border: `1px solid ${hov ? `${feat.color}50` : "rgba(255,255,255,0.06)"}`,
        borderRadius: "4px", padding: "32px",
        position: "relative", overflow: "hidden",
      }}
    >
      {/* left accent bar */}
      <div style={{
        position: "absolute", top: 0, left: 0, width: "3px", bottom: 0,
        background: `linear-gradient(180deg, ${feat.color}, rgba(0,0,0,0))`,
        opacity: hov ? 1 : 0.35, transition: "opacity 0.2s",
      }} />
      {/* corner glow */}
      <div style={{
        position: "absolute", top: "-40px", right: "-40px",
        width: "120px", height: "120px", borderRadius: "50%",
        background: `radial-gradient(circle, ${feat.color}15, transparent 70%)`,
        opacity: hov ? 1 : 0, transition: "opacity 0.3s",
      }} />
      <div style={{ fontSize: "28px", marginBottom: "16px" }}>{feat.icon}</div>
      <div style={{ fontFamily: BEBAS, fontSize: "20px", color: "rgba(255,255,255,0.9)", letterSpacing: "0.06em", marginBottom: "12px" }}>
        {feat.title}
      </div>
      <p style={{ fontFamily: SANS, fontSize: "13px", color: "rgba(255,255,255,0.45)", lineHeight: 1.75, marginBottom: "20px" }}>
        {feat.desc}
      </p>
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
        {feat.tags.map((t) => (
          <span key={t} style={{
            fontFamily: MONO, fontSize: "9px", color: feat.color,
            border: `1px solid ${feat.color}40`,
            borderRadius: "2px", padding: "3px 8px", letterSpacing: "0.08em",
          }}>{t}</span>
        ))}
      </div>
    </div>
  );
}

// ─── Crop card ────────────────────────────────────────────────────────────────
function CropCard({ crop, delay }) {
  const [ref, inView] = useInView();
  const [hov, setHov] = useState(false);
  return (
    <div
      ref={ref}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0) scale(1)" : "translateY(24px) scale(0.97)",
        transition: `opacity 0.6s cubic-bezier(.22,1,.36,1) ${delay}ms, transform 0.6s cubic-bezier(.22,1,.36,1) ${delay}ms, background 0.2s, border-color 0.2s`,
        background: hov ? "rgba(74,222,128,0.04)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${hov ? "rgba(74,222,128,0.28)" : "rgba(255,255,255,0.06)"}`,
        borderRadius: "4px", padding: "28px 24px",
        position: "relative", cursor: "default",
      }}
    >
      <div style={{
        position: "absolute", top: "12px", right: "14px",
        fontFamily: MONO, fontSize: "9px",
        color: crop.color, opacity: 0.7, letterSpacing: "0.12em",
      }}>
        {crop.rank} US
      </div>
      <div style={{ fontSize: "36px", marginBottom: "12px" }}>{crop.icon}</div>
      <div style={{ fontFamily: BEBAS, fontSize: "22px", color: "rgba(255,255,255,0.9)", letterSpacing: "0.05em", marginBottom: "4px" }}>
        {crop.name}
      </div>
      <div style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.08em" }}>
        {crop.acres} acres
      </div>
      <div style={{
        marginTop: "16px", height: "2px", borderRadius: "1px",
        background: `linear-gradient(90deg, ${crop.color}60, transparent)`,
        width: hov ? "100%" : "40%", transition: "width 0.3s ease",
      }} />
    </div>
  );
}

// ─── Footer CTA ───────────────────────────────────────────────────────────────
function FooterCTA() {
  const [ref, inView] = useInView(0.2);
  return (
    <section ref={ref} style={{
      position: "relative", zIndex: 1, overflow: "hidden",
      background: "rgba(74,222,128,0.04)",
      borderTop: "1px solid rgba(74,222,128,0.12)",
      borderBottom: "1px solid rgba(74,222,128,0.12)",
    }}>
      {/* Row-field decoration */}
      <div aria-hidden style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", gap: "18px", padding: "24px 0", opacity: 0.06 }}>
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} style={{
            height: "2px",
            background: `linear-gradient(90deg, transparent, ${G}, transparent)`,
            animation: `lp-row-scroll ${3 + i * 0.4}s linear infinite`,
            animationDelay: `${i * 0.3}s`,
          }} />
        ))}
      </div>
      <div style={{
        position: "relative", maxWidth: "1200px", margin: "0 auto",
        padding: "80px 48px",
        display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(24px)",
        transition: "all 0.8s cubic-bezier(.22,1,.36,1)",
      }}>
        <div style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(74,222,128,0.5)", letterSpacing: "0.2em", marginBottom: "24px" }}>
          START NOW
        </div>
        <h2 style={{
          fontFamily: BEBAS, fontSize: "clamp(40px, 5vw, 64px)",
          color: "rgba(255,255,255,0.95)", letterSpacing: "0.03em",
          lineHeight: 1.05, marginBottom: "16px",
        }}>
          Ready to diagnose your field?
        </h2>
        <p style={{
          fontFamily: SANS, fontSize: "16px", fontWeight: 300,
          color: "rgba(255,255,255,0.4)", marginBottom: "8px", maxWidth: "400px", lineHeight: 1.7,
        }}>
          Launch a simulation in under 30 seconds. No setup required.
        </p>
        <p style={{
          fontFamily: SANS, fontSize: "13px", fontStyle: "italic", fontWeight: 300,
          color: "rgba(255,255,255,0.22)", marginBottom: "40px", maxWidth: "460px", lineHeight: 1.7,
        }}>
          Built by a developer whose family farms in Andhra Pradesh, India.
          Free for US corn farmers during the 2026 growing season.
        </p>
        <CTAButton />
      </div>
    </section>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function Landing() {
  const [heroVisible, setHeroVisible] = useState(false);
  const [mousePos, setMousePos]       = useState({ x: 0.5, y: 0.5 });
  const [statsLabelRef, statsLabelIn] = useInView();
  const [cropsLabelRef, cropsLabelIn] = useInView();
  const [howLabelRef,   howLabelIn]   = useInView(0.1);
  const [featLabelRef,  featLabelIn]  = useInView(0.1);

  useEffect(() => {
    const t = setTimeout(() => setHeroVisible(true), 80);
    const onMouse = (e) => setMousePos({ x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight });
    window.addEventListener("mousemove", onMouse);
    return () => { clearTimeout(t); window.removeEventListener("mousemove", onMouse); };
  }, []);

  // Section padding shorthand
  const SP = { position: "relative", zIndex: 1, padding: "80px 48px", maxWidth: "1200px", margin: "0 auto" };

  return (
    <div style={{ background: BG, minHeight: "100vh", fontFamily: SANS, color: "white", overflowX: "hidden", position: "relative" }}>

      {/* ── Global styles + fonts ─────────────────────────────────── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
        *, *::before, *::after { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #080f09; }
        ::-webkit-scrollbar-thumb { background: rgba(74,222,128,0.3); border-radius: 2px; }

        @keyframes lp-pulse    { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes lp-shimmer  { 0%{background-position:0% 50%} 100%{background-position:200% 50%} }
        @keyframes lp-bounce   { 0%,100%{transform:translateY(0)} 50%{transform:translateY(7px)} }
        @keyframes lp-row-scroll {
          0%   { transform: translateX(-30%); }
          100% { transform: translateX(30%);  }
        }

        /* ── Responsive overrides ─────────────────────────────── */
        @media (max-width: 900px) {
          .lp-stats-grid  { grid-template-columns: 1fr 1fr !important; }
          .lp-feat-grid   { grid-template-columns: 1fr !important; }
          .lp-crops-grid  { grid-template-columns: repeat(3, 1fr) !important; }
        }
        @media (max-width: 900px) {
          .lp-hero-cols   { grid-template-columns: 1fr !important; gap: 48px !important; }
        }
        @media (max-width: 768px) {
          .lp-nav-links   { display: none !important; }
          .lp-sp          { padding: 56px 24px !important; }
          .lp-hero-sec    { padding: 90px 24px 64px !important; min-height: unset !important; }
          .lp-h1          { font-size: clamp(52px, 14vw, 80px) !important; }
          .lp-how-step    { flex-direction: column !important; }
          .lp-how-num     { border-right: none !important; border-bottom: 1px solid rgba(74,222,128,0.1) !important; padding: 20px 28px !important; min-width: unset !important; }
          .lp-footer-cta  { padding: 56px 24px !important; }
        }
        @media (max-width: 560px) {
          .lp-stats-grid  { grid-template-columns: 1fr !important; }
          .lp-crops-grid  { grid-template-columns: 1fr 1fr !important; }
        }
      `}</style>

      {/* ── Mouse-tracking glow (fixed → viewport-relative, subtle) ── */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: `radial-gradient(ellipse 80vw 60vh at ${mousePos.x * 100}% ${mousePos.y * 100}%, rgba(74,222,128,0.05) 0%, transparent 70%)`,
        transition: "background 0.5s ease",
      }} />

      {/* ── Grid texture ──────────────────────────────────────────── */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0, opacity: 0.025,
        backgroundImage: "linear-gradient(rgba(74,222,128,1) 1px, transparent 1px), linear-gradient(90deg, rgba(74,222,128,1) 1px, transparent 1px)",
        backgroundSize: "60px 60px",
      }} />

      {/* ── NAV ───────────────────────────────────────────────────── */}
      <nav style={{
        position: "sticky", top: 0, zIndex: 50,
        padding: "16px 48px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(74,222,128,0.08)",
        background: "rgba(8,15,9,0.92)", backdropFilter: "blur(20px)",
      }}>
        {/* Wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: G, boxShadow: `0 0 12px ${G}`,
            animation: "lp-pulse 2s infinite",
          }} />
          <span style={{ fontFamily: BEBAS, fontSize: "20px", letterSpacing: "0.1em", color: G }}>
            AGROVISUS
          </span>
        </div>
        {/* Links */}
        <div className="lp-nav-links" style={{ display: "flex", alignItems: "center", gap: "32px" }}>
          {[["HOW IT WORKS", "#how"], ["CROPS", "#crops"]].map(([label, href]) => (
            <NavAnchor key={label} label={label} href={href} />
          ))}
          <Link
            to="/simulate"
            style={{
              fontFamily: MONO, fontSize: "10px", letterSpacing: "0.14em",
              color: BG, background: G,
              padding: "9px 20px", borderRadius: "2px",
              textDecoration: "none", fontWeight: 600,
              transition: "opacity 0.2s",
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = "0.85"}
            onMouseLeave={e => e.currentTarget.style.opacity = "1"}
          >
            SIMULATE
          </Link>
        </div>
      </nav>

      {/* ── HERO ──────────────────────────────────────────────────── */}
      <section className="lp-hero-sec" style={{
        position: "relative", zIndex: 1,
        minHeight: "calc(100vh - 57px)",
        display: "flex", flexDirection: "column", justifyContent: "center",
        padding: "100px 48px 80px", maxWidth: "1200px", margin: "0 auto",
      }}>
        {/* Two-column layout: text left, preview card right */}
        <div className="lp-hero-cols" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "64px", alignItems: "center" }}>

          {/* ── Left column: headline + sub + CTA + metrics ── */}
          <div>
            {/* Headline */}
            <FadeUp visible={heroVisible} delay={200}>
              <h1 className="lp-h1" style={{
                fontFamily: BEBAS,
                fontSize: "clamp(64px, 9vw, 120px)",
                lineHeight: 0.92, letterSpacing: "0.02em", marginBottom: "32px",
              }}>
                <span style={{ color: "rgba(255,255,255,0.95)", display: "block" }}>YOUR FIELD</span>
                <span style={{ color: "rgba(255,255,255,0.95)", display: "block" }}>HAS A</span>
                <span style={{
                  display: "block",
                  background: "linear-gradient(135deg, #4ade80 0%, #86efac 50%, #4ade80 100%)",
                  WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
                  backgroundSize: "200%",
                  animation: "lp-shimmer 3s linear infinite",
                }}>DIAGNOSIS.</span>
              </h1>
            </FadeUp>

            {/* Sub */}
            <FadeUp visible={heroVisible} delay={340}>
              <p style={{
                fontSize: "18px", fontWeight: 300,
                color: "rgba(255,255,255,0.45)",
                maxWidth: "520px", lineHeight: 1.75, marginBottom: "40px",
              }}>
                AgroVisus runs a daily field simulation — tracking disease pressure,
                nutrient stress, and water balance — then tells you exactly what it
                will cost you if you don't act, and what you gain if you do.
              </p>
            </FadeUp>

            {/* CTA */}
            <FadeUp visible={heroVisible} delay={480}>
              <div style={{ marginBottom: "16px" }}>
                <CTAButton />
              </div>
            </FadeUp>

            {/* Validation proof point */}
            <FadeUp visible={heroVisible} delay={540}>
              <p style={{
                fontFamily: SANS, fontSize: "12px", fontStyle: "italic",
                color: "rgba(255,255,255,0.28)", marginBottom: "32px", lineHeight: 1.6,
              }}>
                Validated against University of Illinois 274 site-year corn nitrogen trial data.
              </p>
            </FadeUp>

            {/* Free / no signup trust line */}
            <FadeUp visible={heroVisible} delay={580}>
              <div style={{
                fontFamily: MONO, fontSize: "10px", letterSpacing: "0.18em",
                color: "rgba(74,222,128,0.6)", marginBottom: "36px",
                textTransform: "uppercase",
              }}>
                Free · No signup required · No credit card
              </div>
            </FadeUp>

            {/* Metrics strip */}
            <FadeUp visible={heroVisible} delay={640}>
              <div style={{ display: "flex", gap: "28px", flexWrap: "wrap" }}>
                {[
                  { label: "Crops modeled",   val: "5" },
                  { label: "Tests passing",   val: "167" },
                  { label: "Data sources",    val: "FAO-56 · DSSAT · USDA" },
                ].map((m) => (
                  <div key={m.label} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "1px", height: "32px", background: "rgba(74,222,128,0.25)" }} />
                    <div>
                      <div style={{ fontFamily: BEBAS, fontSize: "20px", color: G, letterSpacing: "0.05em" }}>{m.val}</div>
                      <div style={{ fontFamily: MONO, fontSize: "9px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.1em" }}>{m.label}</div>
                    </div>
                  </div>
                ))}
              </div>
            </FadeUp>
          </div>

          {/* ── Right column: live output preview card ── */}
          <FadeUp visible={heroVisible} delay={700}>
            <div>
              <div style={{
                fontFamily: MONO, fontSize: "9px", letterSpacing: "0.2em",
                color: "rgba(74,222,128,0.55)", textTransform: "uppercase",
                marginBottom: "12px",
              }}>
                Live Simulation Output
              </div>
              <div style={{
                background: "#0a1a0a",
                border: "1px solid #22c55e",
                borderRadius: "6px",
                boxShadow: "0 0 40px rgba(34,197,94,0.12), 0 8px 32px rgba(0,0,0,0.5)",
                overflow: "hidden",
                fontFamily: SANS,
              }}>
                {/* Card header */}
                <div style={{
                  padding: "14px 18px 12px",
                  borderBottom: "1px solid rgba(74,222,128,0.15)",
                  background: "rgba(74,222,128,0.04)",
                }}>
                  <div style={{ fontSize: "13px", fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: "3px" }}>
                    🌽 Central Illinois · May 2025
                  </div>
                  <div style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(255,255,255,0.35)", letterSpacing: "0.06em" }}>
                    CORN · V8 · DRY CONDITIONS
                  </div>
                </div>

                {/* Field Health + Yield */}
                <div style={{
                  display: "grid", gridTemplateColumns: "1fr 1fr",
                  padding: "16px 18px", gap: "12px",
                  borderBottom: "1px solid rgba(74,222,128,0.1)",
                }}>
                  <div>
                    <div style={{ fontFamily: MONO, fontSize: "9px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.12em", marginBottom: "5px" }}>FIELD HEALTH</div>
                    <div style={{ fontFamily: BEBAS, fontSize: "38px", color: "#f97316", lineHeight: 1 }}>D</div>
                    <div style={{ fontSize: "11px", color: "#f97316", marginTop: "2px" }}>High Stress</div>
                  </div>
                  <div>
                    <div style={{ fontFamily: MONO, fontSize: "9px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.12em", marginBottom: "5px" }}>FINAL YIELD</div>
                    <div style={{ fontFamily: BEBAS, fontSize: "32px", color: "#4ade80", lineHeight: 1 }}>91 bu/acre</div>
                    <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)", marginTop: "2px" }}>vs 180 potential</div>
                  </div>
                </div>

                {/* Alert */}
                <div style={{
                  padding: "14px 18px",
                  borderBottom: "1px solid rgba(74,222,128,0.1)",
                  background: "rgba(127,29,29,0.15)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <span style={{
                      fontFamily: MONO, fontSize: "9px", fontWeight: 700,
                      letterSpacing: "0.1em", padding: "3px 8px", borderRadius: "2px",
                      background: "#7f1d1d", color: "#fca5a5",
                    }}>⚠ HIGH</span>
                    <span style={{ fontSize: "13px", fontWeight: 600, color: "rgba(255,255,255,0.8)" }}>
                      Severe Nitrogen Deficiency
                    </span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                    <div style={{ fontSize: "12px", color: "#4ade80", fontWeight: 600 }}>Revenue at risk: $203/acre</div>
                    <div style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(255,255,255,0.4)", letterSpacing: "0.04em" }}>Yield loss: 45.0 bu/acre</div>
                    <div style={{ fontFamily: MONO, fontSize: "10px", color: "rgba(255,255,255,0.4)", letterSpacing: "0.04em" }}>Treatment ROI: +467% (medium efficacy)</div>
                  </div>
                </div>

                {/* CTA inside card */}
                <div style={{ padding: "14px 18px" }}>
                  <Link
                    to="/simulate"
                    onClick={() => {
                      try { sessionStorage.setItem('agrovisus_load_scenario', 'problem'); } catch {}
                    }}
                    style={{
                      display: "inline-flex", alignItems: "center", gap: "8px",
                      background: G, color: BG,
                      fontFamily: SANS, fontWeight: 700, fontSize: "13px",
                      padding: "10px 20px", borderRadius: "3px",
                      textDecoration: "none", width: "100%", justifyContent: "center",
                    }}
                  >
                    Run this simulation →
                  </Link>
                </div>
              </div>
            </div>
          </FadeUp>

        </div>{/* end hero grid */}

        {/* Scroll hint */}
        <div style={{
          position: "absolute", bottom: "32px", left: "48px",
          opacity: heroVisible ? 0.4 : 0, transition: "opacity 1s 1.5s",
          fontFamily: MONO, fontSize: "9px",
          color: "rgba(74,222,128,0.6)", letterSpacing: "0.15em",
          animation: "lp-bounce 2.4s 2s infinite",
        }}>
          ↓ SCROLL
        </div>
      </section>

      {/* ── STATS ─────────────────────────────────────────────────── */}
      <section className="lp-sp" style={SP}>
        <SectionLabel label="ENGINE VALIDATION" refProp={statsLabelRef} inView={statsLabelIn} />
        <div className="lp-stats-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px" }}>
          {STATS.map((s, i) => <StatCard key={s.unit} stat={s} delay={i * 90} />)}
        </div>
      </section>

      {/* ── HOW IT WORKS ──────────────────────────────────────────── */}
      <section id="how" className="lp-sp" style={SP}>
        <SectionLabel label="HOW IT WORKS" refProp={howLabelRef} inView={howLabelIn} />
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {HOW_STEPS.map((step, i) => (
            <HowCard key={step.num} step={step} delay={i * 130} parentInView={howLabelIn} />
          ))}
        </div>
      </section>

      {/* ── WHAT IT DOES ──────────────────────────────────────────── */}
      <section className="lp-sp" style={SP}>
        <SectionLabel label="WHAT IT DOES" refProp={featLabelRef} inView={featLabelIn} />
        <div className="lp-feat-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          {FEATURES.map((f, i) => <FeatureCard key={f.title} feat={f} delay={i * 90} />)}
        </div>
      </section>

      {/* ── CROPS ─────────────────────────────────────────────────── */}
      <section id="crops" className="lp-sp" style={SP}>
        <SectionLabel label="SUPPORTED CROPS" refProp={cropsLabelRef} inView={cropsLabelIn} />
        <p style={{
          opacity: cropsLabelIn ? 1 : 0, transition: "opacity 0.7s 0.15s",
          fontFamily: SANS, fontSize: "14px",
          color: "rgba(255,255,255,0.3)", marginBottom: "40px",
          maxWidth: "480px", lineHeight: 1.7,
        }}>
          Covering 223M acres of US cropland — the five highest-value row crops
          with scientifically grounded templates from FAO-56, DSSAT v4.8, and USDA-ARS.
        </p>
        <div className="lp-crops-grid" style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "12px" }}>
          {CROPS.map((c, i) => <CropCard key={c.name} crop={c} delay={i * 80} />)}
        </div>
      </section>

      {/* ── FOOTER CTA ────────────────────────────────────────────── */}
      <FooterCTA />

      {/* ── Minimal footer bar ────────────────────────────────────── */}
      <footer style={{
        position: "relative", zIndex: 1,
        borderTop: "1px solid rgba(74,222,128,0.06)",
        padding: "24px 48px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexWrap: "wrap", gap: "12px",
      }}>
        <span style={{ fontFamily: BEBAS, fontSize: "15px", color: "rgba(74,222,128,0.25)", letterSpacing: "0.1em" }}>
          AGROVISUS
        </span>
        <span style={{ fontFamily: MONO, fontSize: "9px", color: "rgba(255,255,255,0.12)", letterSpacing: "0.1em" }}>
          BUILT ON FAO-56 · DSSAT v4.8 · USDA-ARS · ICAR
        </span>
      </footer>
    </div>
  );
}

// ─── Tiny helpers defined after Landing (hoisted by JS) ───────────────────────
function FadeUp({ visible, delay, children }) {
  return (
    <div style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(22px)",
      transition: `opacity 0.85s cubic-bezier(.22,1,.36,1) ${delay}ms, transform 0.85s cubic-bezier(.22,1,.36,1) ${delay}ms`,
    }}>
      {children}
    </div>
  );
}

function NavAnchor({ label, href }) {
  const [hov, setHov] = useState(false);
  return (
    <a
      href={href}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        fontFamily: MONO, fontSize: "10px", letterSpacing: "0.18em",
        color: hov ? G : "rgba(74,222,128,0.5)",
        textDecoration: "none", transition: "color 0.2s",
      }}
    >
      {label}
    </a>
  );
}

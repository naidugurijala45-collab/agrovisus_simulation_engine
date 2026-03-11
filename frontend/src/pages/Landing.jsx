import { useState, useEffect, useRef } from "react";

const crops = [
  { name: "Corn", icon: "🌽", acres: "91.5M", rank: "#1", color: "#f59e0b" },
  { name: "Soybean", icon: "🫘", acres: "86.1M", rank: "#2", color: "#84cc16" },
  { name: "Wheat", icon: "🌾", acres: "33.8M", rank: "#3", color: "#d97706" },
  { name: "Rice", icon: "🌿", acres: "2.87M", rank: "#6", color: "#34d399" },
  { name: "Sorghum", icon: "🌱", acres: "5.5M", rank: "#7", color: "#a3e635" },
];

const stats = [
  { value: "6,223", unit: "kg/ha", label: "Validated corn yield accuracy", sub: "vs 8,992 AquaCrop upper bound" },
  { value: "31%", unit: "gap", label: "From theoretical maximum", sub: "explained by real stress conditions" },
  { value: "110", unit: "tests", label: "All passing, zero regressions", sub: "DSSAT · FAO-56 · USDA-ARS validated" },
  { value: "4", unit: "regions", label: "US Corn Belt coverage", sub: "OH · IN · IL · IA · KS · GA and more" },
];

function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, inView];
}

function StatCard({ value, unit, label, sub, delay }) {
  const [ref, inView] = useInView();
  return (
    <div ref={ref} style={{
      opacity: inView ? 1 : 0,
      transform: inView ? "translateY(0)" : "translateY(32px)",
      transition: `all 0.7s cubic-bezier(.22,1,.36,1) ${delay}ms`,
      background: "rgba(255,255,255,0.02)",
      border: "1px solid rgba(74,222,128,0.1)",
      borderTop: "2px solid rgba(74,222,128,0.4)",
      borderRadius: "2px",
      padding: "32px 28px",
      position: "relative",
      overflow: "hidden",
    }}>
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "1px",
        background: "linear-gradient(90deg, transparent, rgba(74,222,128,0.6), transparent)",
      }} />
      <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "8px" }}>
        <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "52px", color: "#4ade80", lineHeight: 1, letterSpacing: "0.02em" }}>
          {value}
        </span>
        <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "22px", color: "rgba(74,222,128,0.5)", letterSpacing: "0.05em" }}>
          {unit}
        </span>
      </div>
      <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "13px", color: "rgba(255,255,255,0.7)", marginBottom: "4px", fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: "rgba(74,222,128,0.4)", letterSpacing: "0.08em" }}>
        {sub}
      </div>
    </div>
  );
}

function CropCard({ crop, delay }) {
  const [ref, inView] = useInView();
  const [hovered, setHovered] = useState(false);
  return (
    <div ref={ref} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0) scale(1)" : "translateY(24px) scale(0.97)",
        transition: `all 0.6s cubic-bezier(.22,1,.36,1) ${delay}ms, background 0.2s, border 0.2s`,
        background: hovered ? "rgba(74,222,128,0.05)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${hovered ? "rgba(74,222,128,0.3)" : "rgba(255,255,255,0.06)"}`,
        borderRadius: "4px",
        padding: "28px 24px",
        cursor: "default",
        position: "relative",
      }}>
      <div style={{
        position: "absolute", top: "12px", right: "14px",
        fontFamily: "'DM Mono', monospace", fontSize: "9px",
        color: crop.color, opacity: 0.7, letterSpacing: "0.12em",
      }}>
        {crop.rank} US
      </div>
      <div style={{ fontSize: "36px", marginBottom: "12px" }}>{crop.icon}</div>
      <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "22px", color: "rgba(255,255,255,0.9)", letterSpacing: "0.05em", marginBottom: "4px" }}>
        {crop.name}
      </div>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.08em" }}>
        {crop.acres} acres
      </div>
      <div style={{
        marginTop: "16px", height: "2px", borderRadius: "1px",
        background: `linear-gradient(90deg, ${crop.color}60, transparent)`,
        width: hovered ? "100%" : "40%", transition: "width 0.3s ease",
      }} />
    </div>
  );
}

export default function AgroVisusLanding() {
  const [heroVisible, setHeroVisible] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [statsRef, statsInView] = useInView();
  const [cropsRef, cropsInView] = useInView();

  useEffect(() => {
    setTimeout(() => setHeroVisible(true), 100);
    const handleMouse = (e) => setMousePos({ x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight });
    window.addEventListener("mousemove", handleMouse);
    return () => window.removeEventListener("mousemove", handleMouse);
  }, []);

  return (
    <div style={{
      background: "#080f09",
      minHeight: "100vh",
      fontFamily: "'DM Sans', sans-serif",
      color: "white",
      overflowX: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #080f09; }
        ::-webkit-scrollbar-thumb { background: rgba(74,222,128,0.3); border-radius: 2px; }
      `}</style>

      {/* Ambient glow that follows mouse */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: `radial-gradient(ellipse 80vw 60vh at ${mousePos.x * 100}% ${mousePos.y * 100}%, rgba(74,222,128,0.04) 0%, transparent 70%)`,
        transition: "background 0.3s ease",
      }} />

      {/* Grid overlay */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0, opacity: 0.025,
        backgroundImage: "linear-gradient(rgba(74,222,128,1) 1px, transparent 1px), linear-gradient(90deg, rgba(74,222,128,1) 1px, transparent 1px)",
        backgroundSize: "60px 60px",
      }} />

      {/* NAV */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        padding: "20px 48px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(74,222,128,0.08)",
        background: "rgba(8,15,9,0.85)", backdropFilter: "blur(20px)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: "#4ade80",
            boxShadow: "0 0 12px #4ade80",
            animation: "pulse 2s infinite",
          }} />
          <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "22px", letterSpacing: "0.1em", color: "#4ade80" }}>
            AGROVISUS
          </span>
        </div>
        <div style={{
          fontFamily: "'DM Mono', monospace", fontSize: "10px",
          color: "rgba(74,222,128,0.5)", letterSpacing: "0.15em",
        }}>
          SIMULATION ENGINE v2.3
        </div>
      </nav>

      {/* HERO */}
      <section style={{
        position: "relative", zIndex: 1,
        minHeight: "100vh",
        display: "flex", flexDirection: "column", justifyContent: "center",
        padding: "120px 48px 80px",
        maxWidth: "1200px", margin: "0 auto",
      }}>
        {/* Eyebrow */}
        <div style={{
          opacity: heroVisible ? 1 : 0,
          transform: heroVisible ? "translateY(0)" : "translateY(16px)",
          transition: "all 0.8s cubic-bezier(.22,1,.36,1) 0.1s",
          display: "flex", alignItems: "center", gap: "12px", marginBottom: "32px",
        }}>
          <div style={{ width: "32px", height: "1px", background: "rgba(74,222,128,0.5)" }} />
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "11px", color: "rgba(74,222,128,0.6)", letterSpacing: "0.2em" }}>
            PRECISION AGRONOMIC INTELLIGENCE
          </span>
        </div>

        {/* Headline */}
        <h1 style={{
          opacity: heroVisible ? 1 : 0,
          transform: heroVisible ? "translateY(0)" : "translateY(24px)",
          transition: "all 0.9s cubic-bezier(.22,1,.36,1) 0.2s",
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: "clamp(64px, 10vw, 128px)",
          lineHeight: 0.92,
          letterSpacing: "0.02em",
          marginBottom: "32px",
        }}>
          <span style={{ color: "rgba(255,255,255,0.95)", display: "block" }}>YOUR FIELD</span>
          <span style={{ color: "rgba(255,255,255,0.95)", display: "block" }}>HAS A</span>
          <span style={{
            display: "block",
            background: "linear-gradient(135deg, #4ade80 0%, #86efac 50%, #4ade80 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            backgroundSize: "200%",
            animation: "shimmer 3s infinite linear",
          }}>DIAGNOSIS.</span>
        </h1>

        {/* Subheadline */}
        <p style={{
          opacity: heroVisible ? 1 : 0,
          transform: heroVisible ? "translateY(0)" : "translateY(20px)",
          transition: "all 0.9s cubic-bezier(.22,1,.36,1) 0.35s",
          fontSize: "18px", fontWeight: 300,
          color: "rgba(255,255,255,0.45)",
          maxWidth: "520px", lineHeight: 1.7,
          marginBottom: "48px",
        }}>
          AgroVisus runs a daily field simulation — tracking disease pressure, nutrient stress, and water balance — then tells you exactly what it will cost you if you don't act, and what you gain if you do.
        </p>

        {/* Metrics strip */}
        <div style={{
          opacity: heroVisible ? 1 : 0,
          transform: heroVisible ? "translateY(0)" : "translateY(16px)",
          transition: "all 0.9s cubic-bezier(.22,1,.36,1) 0.5s",
          display: "flex", gap: "32px", flexWrap: "wrap",
        }}>
          {[
            { label: "Crops modeled", val: "5" },
            { label: "US regions covered", val: "4" },
            { label: "Data sources", val: "FAO-56 · DSSAT · USDA" },
          ].map((m, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={{ width: "1px", height: "32px", background: "rgba(74,222,128,0.25)" }} />
              <div>
                <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "20px", color: "#4ade80", letterSpacing: "0.05em" }}>{m.val}</div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "9px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.1em" }}>{m.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Scroll hint */}
        <div style={{
          position: "absolute", bottom: "40px", left: "48px",
          opacity: heroVisible ? 0.4 : 0, transition: "opacity 1s 1.2s",
          display: "flex", alignItems: "center", gap: "8px",
          fontFamily: "'DM Mono', monospace", fontSize: "9px",
          color: "rgba(74,222,128,0.6)", letterSpacing: "0.15em",
          animation: "bounce 2s 2s infinite",
        }}>
          ↓ SCROLL
        </div>
      </section>

      {/* STATS */}
      <section style={{ position: "relative", zIndex: 1, padding: "80px 48px", maxWidth: "1200px", margin: "0 auto" }}>
        <div ref={statsRef} style={{
          opacity: statsInView ? 1 : 0,
          transform: statsInView ? "translateY(0)" : "translateY(24px)",
          transition: "all 0.7s ease",
          display: "flex", alignItems: "center", gap: "16px", marginBottom: "48px",
        }}>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: "rgba(74,222,128,0.5)", letterSpacing: "0.2em" }}>
            ENGINE VALIDATION
          </span>
          <div style={{ flex: 1, height: "1px", background: "rgba(74,222,128,0.1)" }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
          {stats.map((s, i) => <StatCard key={i} {...s} delay={i * 100} />)}
        </div>
      </section>

      {/* CROPS */}
      <section style={{ position: "relative", zIndex: 1, padding: "80px 48px 120px", maxWidth: "1200px", margin: "0 auto" }}>
        <div ref={cropsRef} style={{
          opacity: cropsInView ? 1 : 0,
          transform: cropsInView ? "translateY(0)" : "translateY(24px)",
          transition: "all 0.7s ease",
          display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px",
        }}>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: "rgba(74,222,128,0.5)", letterSpacing: "0.2em" }}>
            SUPPORTED CROPS
          </span>
          <div style={{ flex: 1, height: "1px", background: "rgba(74,222,128,0.1)" }} />
        </div>
        <p style={{
          opacity: cropsInView ? 1 : 0, transition: "opacity 0.7s 0.1s",
          fontFamily: "'DM Sans', sans-serif", fontSize: "14px",
          color: "rgba(255,255,255,0.3)", marginBottom: "40px", maxWidth: "480px",
        }}>
          Covering 223M acres of US cropland — the five highest-value row crops with scientifically grounded templates from FAO-56, DSSAT v4.8, and USDA-ARS.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px" }}>
          {crops.map((c, i) => <CropCard key={i} crop={c} delay={i * 80} />)}
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{
        position: "relative", zIndex: 1,
        borderTop: "1px solid rgba(74,222,128,0.08)",
        padding: "32px 48px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexWrap: "wrap", gap: "16px",
      }}>
        <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: "16px", color: "rgba(74,222,128,0.3)", letterSpacing: "0.1em" }}>
          AGROVISUS
        </span>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "9px", color: "rgba(255,255,255,0.15)", letterSpacing: "0.1em" }}>
          BUILT ON FAO-56 · DSSAT v4.8 · USDA-ARS · ICAR
        </span>
      </footer>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes shimmer { 0% { background-position: 0% 50%; } 100% { background-position: 200% 50%; } }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(6px); } }
      `}</style>
    </div>
  );
}

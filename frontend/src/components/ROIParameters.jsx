import { useState } from "react";

const cropDefaults = { corn: 4.50, soybean: 11.00, wheat: 5.50 };

/**
 * ROIParameters — polished mono-UI input block for ROI simulation fields.
 *
 * Props:
 *   fieldAcres            {number|string}
 *   treatmentCostPerAcre  {number|string}
 *   commodityPrice        {number|string}
 *   onChange              {(field, value) => void}
 */
export default function ROIParameters({ fieldAcres, treatmentCostPerAcre, commodityPrice, onChange }) {
  const [focusedField, setFocusedField] = useState(null);

  const price = parseFloat(commodityPrice) || null;
  const cost  = parseFloat(treatmentCostPerAcre) || null;
  const roi   = price && cost
    ? ((price * 200 * 0.05 - cost) / cost * 100).toFixed(0)
    : null;

  const fields = [
    { label: "Field Size",       unit: "acres",  value: fieldAcres,           key: "field_acres",             placeholder: "100" },
    { label: "Treatment Cost",   unit: "$/acre", value: treatmentCostPerAcre, key: "treatment_cost_per_acre", placeholder: "25" },
    { label: "Commodity Price",  unit: "$/bu",   value: commodityPrice,       key: "commodity_price_usd_bu",  placeholder: "optional", optional: true },
  ];

  return (
    <div style={{
      background: "linear-gradient(135deg, #0a1a0e 0%, #0d2010 50%, #0a1a0e 100%)",
      border: "1px solid rgba(74, 222, 128, 0.15)",
      borderRadius: "16px",
      padding: "28px 32px",
      fontFamily: "'DM Mono', 'Fira Code', monospace",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Background grid */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.04,
        backgroundImage: "linear-gradient(rgba(74,222,128,0.8) 1px, transparent 1px), linear-gradient(90deg, rgba(74,222,128,0.8) 1px, transparent 1px)",
        backgroundSize: "32px 32px", pointerEvents: "none",
      }} />

      {/* Glow orb */}
      <div style={{
        position: "absolute", top: -60, right: -40, width: 180, height: 180,
        background: "radial-gradient(circle, rgba(74,222,128,0.08) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "24px" }}>
        <div style={{
          width: "3px", height: "18px", borderRadius: "2px",
          background: "linear-gradient(180deg, #4ade80, #16a34a)",
        }} />
        <span style={{
          color: "#4ade80", fontSize: "11px", fontWeight: 600,
          letterSpacing: "0.18em", textTransform: "uppercase",
        }}>ROI Parameters</span>
        <div style={{
          marginLeft: "auto", background: "rgba(74,222,128,0.08)",
          border: "1px solid rgba(74,222,128,0.2)", borderRadius: "6px",
          padding: "3px 10px", color: "rgba(74,222,128,0.6)", fontSize: "10px",
          letterSpacing: "0.1em",
        }}>LIVE CALC</div>
      </div>

      {/* Input fields */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "14px", marginBottom: "20px" }}>
        {fields.map(({ label, unit, value, key, placeholder, optional }) => (
          <div key={key}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "8px" }}>
              <label style={{
                color: focusedField === key ? "#4ade80" : "rgba(255,255,255,0.5)",
                fontSize: "10px", fontWeight: 600, letterSpacing: "0.12em",
                textTransform: "uppercase", transition: "color 0.2s",
              }}>{label}</label>
              <span style={{ color: "rgba(74,222,128,0.4)", fontSize: "9px", letterSpacing: "0.08em" }}>{unit}</span>
            </div>
            <div style={{
              position: "relative",
              border: `1px solid ${focusedField === key ? "rgba(74,222,128,0.5)" : "rgba(74,222,128,0.12)"}`,
              borderRadius: "10px",
              background: focusedField === key ? "rgba(74,222,128,0.06)" : "rgba(255,255,255,0.03)",
              transition: "all 0.2s",
              boxShadow: focusedField === key ? "0 0 0 3px rgba(74,222,128,0.08), inset 0 1px 0 rgba(74,222,128,0.1)" : "none",
            }}>
              <input
                type="number"
                value={value ?? ""}
                onChange={e => onChange(key, e.target.value === "" ? "" : parseFloat(e.target.value))}
                onFocus={() => setFocusedField(key)}
                onBlur={() => setFocusedField(null)}
                placeholder={placeholder}
                style={{
                  width: "100%", background: "transparent", border: "none", outline: "none",
                  color: optional && !value ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.9)",
                  fontSize: "15px", fontWeight: 500, padding: "11px 14px",
                  fontFamily: "inherit", boxSizing: "border-box",
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Quick-fill chips */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "20px", flexWrap: "wrap" }}>
        <span style={{ color: "rgba(255,255,255,0.25)", fontSize: "9px", letterSpacing: "0.1em", marginRight: "2px" }}>PRICE DEFAULTS</span>
        {Object.entries(cropDefaults).map(([crop, price]) => (
          <button
            key={crop}
            onClick={() => onChange("commodity_price_usd_bu", price)}
            style={{
              background: parseFloat(commodityPrice) === price ? "rgba(74,222,128,0.15)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${parseFloat(commodityPrice) === price ? "rgba(74,222,128,0.4)" : "rgba(255,255,255,0.08)"}`,
              borderRadius: "6px", padding: "4px 10px", cursor: "pointer",
              color: parseFloat(commodityPrice) === price ? "#4ade80" : "rgba(255,255,255,0.35)",
              fontSize: "10px", fontWeight: 600, letterSpacing: "0.08em",
              textTransform: "capitalize", transition: "all 0.15s", fontFamily: "inherit",
            }}
          >
            {crop} ${price}
          </button>
        ))}
      </div>

      {/* Live ROI preview */}
      {roi && (
        <div style={{
          background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.2)",
          borderRadius: "10px", padding: "12px 16px",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          animation: "roiIn 0.3s ease",
        }}>
          <span style={{ color: "rgba(255,255,255,0.45)", fontSize: "10px", letterSpacing: "0.1em" }}>
            EST. TREATMENT ROI
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
            <span style={{
              color: parseInt(roi) > 100 ? "#4ade80" : "#facc15",
              fontSize: "22px", fontWeight: 700, lineHeight: 1,
            }}>{roi}%</span>
            <span style={{ color: "rgba(74,222,128,0.5)", fontSize: "10px" }}>projected</span>
          </div>
        </div>
      )}

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500;600&display=swap');
        @keyframes roiIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
        input::placeholder { color: rgba(255,255,255,0.18) !important; }
      `}</style>
    </div>
  );
}

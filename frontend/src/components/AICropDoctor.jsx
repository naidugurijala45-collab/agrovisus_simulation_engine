import { useEffect, useRef, useState } from 'react';
import api from '../api/client';

function CropDoctorIcon({ size = 20, color = '#3B6D11' }) {
    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
            <path
                d="M12 3c-1.5 3-5 5-5 9a5 5 0 0010 0c0-4-3.5-6-5-9z"
                stroke={color} strokeWidth="1.5"
                fill={color === '#fff' ? 'rgba(255,255,255,.15)' : '#EAF3DE'}
            />
            <path d="M12 8v4M10 14h4" stroke={color} strokeWidth="1.3" strokeLinecap="round" />
            <path
                d="M8 20h8"
                stroke={color === '#fff' ? 'rgba(255,255,255,.5)' : '#639922'}
                strokeWidth="1.2" strokeLinecap="round"
            />
            <circle cx="18" cy="5" r="2.5" fill="#4FD966" />
            <path d="M17.2 5l.6.6 1.2-1.2" stroke="#fff" strokeWidth="1"
                strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

function buildFieldContext(result, form, groupedRules) {
    const alerts = (groupedRules || []).map(r => ({
        rule_name:            r.name || r.id,
        severity:             r.severity || 'Moderate',
        yield_impact_percent: r.roi?.estimated_yield_loss_bu_acre
            ? parseFloat(((r.roi.estimated_yield_loss_bu_acre / 180) * 100).toFixed(1))
            : 5.0,
        days_active: r.daysActive || 1,
        advisory:    r.recommendation || '',
    }));
    const topRoi = groupedRules?.find(r => r.roi)?.roi;
    return {
        crop_type:         form?.crop_template || 'corn',
        growth_stage:      result?.final_growth_stage || form?.initial_growth_stage || 'V8',
        state_code:        form?.state_code || 'IL',
        sim_days_run:      result?.daily_data?.length || form?.sim_days || 90,
        final_yield_kg_ha: result?.final_yield_kg_ha ?? 0,
        triggered_alerts:  alerts,
        roi: topRoi ? {
            recommendation_strength:  topRoi.recommendation_strength || 'Monitor',
            revenue_at_risk_per_acre: topRoi.revenue_at_risk_per_acre ?? 0,
            roi_mid:                  topRoi.roi_mid ?? 0,
        } : null,
    };
}

const SUGGESTIONS = [
    'What should I do about the top alert?',
    'Is my yield on track for this stage?',
    'What\'s my biggest risk right now?',
    'How can I improve nitrogen uptake?',
];

function Bubble({ msg }) {
    const isUser = msg.role === 'user';
    return (
        <div style={{ display:'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginBottom: 10 }}>
            {!isUser && (
                <div style={{
                    width:28, height:28, borderRadius:'50%', background:'#EAF3DE',
                    display:'flex', alignItems:'center', justifyContent:'center',
                    flexShrink:0, marginRight:8, marginTop:2,
                }}>
                    <CropDoctorIcon size={15} />
                </div>
            )}
            <div style={{
                maxWidth:'82%', padding:'9px 13px',
                borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                background: isUser ? 'var(--green-600, #16a34a)' : 'var(--bg-secondary)',
                color: isUser ? '#fff' : 'var(--text-primary)',
                fontSize:13, lineHeight:1.55,
                border: isUser ? 'none' : '1px solid var(--border)',
            }}>
                {msg.content}
                {msg.loading && (
                    <span style={{ display:'inline-flex', gap:3, marginLeft:6, verticalAlign:'middle' }}>
                        {[0,1,2].map(i => (
                            <span key={i} style={{
                                width:5, height:5, borderRadius:'50%',
                                background:'var(--green-400)',
                                animation:`acd-dot .9s ${i*0.2}s infinite`,
                            }} />
                        ))}
                    </span>
                )}
            </div>
        </div>
    );
}

export default function AICropDoctor({ result, form, groupedRules }) {
    const [open, setOpen]         = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput]       = useState('');
    const [loading, setLoading]   = useState(false);
    const [error, setError]       = useState(null);
    const bottomRef               = useRef(null);
    const inputRef                = useRef(null);
    const hasResult               = !!result;

    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages]);
    useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 120); }, [open]);

    useEffect(() => {
        if (open && hasResult && messages.length === 0) {
            const ctx   = buildFieldContext(result, form, groupedRules);
            const crop  = ctx.crop_type.charAt(0).toUpperCase() + ctx.crop_type.slice(1);
            const yBu   = (ctx.final_yield_kg_ha / 62.77).toFixed(0);
            const count = ctx.triggered_alerts.length;
            setMessages([{ role:'assistant', content:
                `Hi! I'm your AI Crop Doctor. Your ${crop} simulation finished at ${yBu} bu/acre with ${count} active alert${count!==1?'s':''}. What would you like to know?`
            }]);
        }
    }, [open, hasResult]); // eslint-disable-line react-hooks/exhaustive-deps

    async function send(text) {
        const msg = (text || input).trim();
        if (!msg || loading) return;
        setInput(''); setError(null);
        setMessages(prev => [...prev, { role:'user', content:msg }, { role:'assistant', content:'', loading:true }]);
        setLoading(true);
        try {
            const { data } = await api.post('/chat', {
                message:       msg,
                field_context: buildFieldContext(result, form, groupedRules),
            });
            setMessages(prev => [...prev.slice(0,-1), { role:'assistant', content:data.reply }]);
        } catch (e) {
            setMessages(prev => prev.slice(0,-1));
            setError(e.response?.data?.detail || e.message || 'Failed to reach AI Crop Doctor.');
        } finally { setLoading(false); }
    }

    function handleKey(e) { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send(); } }

    return (
        <>
            <style>{`
                @keyframes acd-dot{0%,80%,100%{opacity:.2;transform:scale(.8)}40%{opacity:1;transform:scale(1)}}
                @keyframes acd-in{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
                .acd-panel{animation:acd-in .18s ease}
            `}</style>

            {/* Trigger chip */}
            <button onClick={() => setOpen(o=>!o)} disabled={!hasResult}
                title={hasResult ? 'Ask AI Crop Doctor' : 'Run a simulation first'}
                style={{
                    display:'flex', alignItems:'center', gap:10,
                    background:'var(--bg-card)', width:'100%',
                    border: open ? '1.5px solid var(--green-500)' : '1px solid var(--border)',
                    borderRadius:12, padding:'9px 14px',
                    cursor: hasResult ? 'pointer' : 'not-allowed',
                    opacity: hasResult ? 1 : 0.45, transition:'border-color .15s,opacity .15s',
                }}>
                <div style={{ width:36, height:36, borderRadius:9, background:'#EAF3DE',
                    display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <CropDoctorIcon size={20} />
                </div>
                <div style={{ textAlign:'left', flex:1 }}>
                    <div style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)' }}>AI Crop Doctor</div>
                    <div style={{ fontSize:11, color:'var(--text-muted)' }}>
                        {hasResult ? 'Ask about your field' : 'Run simulation to unlock'}
                    </div>
                </div>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none"
                    style={{ color:'var(--text-muted)', transition:'transform .2s', transform: open?'rotate(180deg)':'none' }}>
                    <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
            </button>

            {/* Chat panel */}
            {open && hasResult && (
                <div className="acd-panel" style={{
                    background:'var(--bg-card)', border:'1px solid var(--border)',
                    borderRadius:14, overflow:'hidden',
                    display:'flex', flexDirection:'column', height:420,
                }}>
                    {/* Header */}
                    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'12px 14px',
                        borderBottom:'1px solid var(--border)', flexShrink:0 }}>
                        <div style={{ width:30, height:30, borderRadius:8, background:'#EAF3DE',
                            display:'flex', alignItems:'center', justifyContent:'center' }}>
                            <CropDoctorIcon size={16} />
                        </div>
                        <div style={{ flex:1 }}>
                            <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)' }}>AI Crop Doctor</div>
                            <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                                <span style={{ width:6, height:6, borderRadius:'50%', background:'#4FD966', display:'inline-block' }}/>
                                <span style={{ fontSize:10, color:'var(--text-muted)' }}>Online · Powered by Claude</span>
                            </div>
                        </div>
                        <button onClick={() => { setMessages([]); setError(null); }}
                            style={{ background:'none', border:'none', color:'var(--text-muted)', cursor:'pointer', fontSize:11 }}>
                            Clear
                        </button>
                    </div>

                    {/* Messages */}
                    <div style={{ flex:1, overflowY:'auto', padding:'14px 14px 8px' }}>
                        {messages.map((m,i) => <Bubble key={i} msg={m} />)}
                        {messages.length <= 1 && !loading && (
                            <div style={{ marginTop:10 }}>
                                <div style={{ fontSize:10, color:'var(--text-muted)', marginBottom:6, letterSpacing:'0.5px', textTransform:'uppercase' }}>Suggested</div>
                                <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
                                    {SUGGESTIONS.map(s => (
                                        <button key={s} onClick={() => send(s)} style={{
                                            background:'var(--bg-secondary)', border:'1px solid var(--border)',
                                            borderRadius:8, padding:'7px 11px', fontSize:12,
                                            color:'var(--text-secondary)', cursor:'pointer', textAlign:'left',
                                            transition:'border-color .15s,color .15s',
                                        }}
                                        onMouseEnter={e=>{e.target.style.borderColor='var(--green-500)';e.target.style.color='var(--text-primary)';}}
                                        onMouseLeave={e=>{e.target.style.borderColor='var(--border)';e.target.style.color='var(--text-secondary)';}}>
                                            {s}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                        {error && (
                            <div style={{ margin:'8px 0', padding:'8px 12px', background:'var(--red-glow)',
                                border:'1px solid rgba(248,113,113,.25)', borderRadius:8,
                                fontSize:12, color:'var(--red-400)' }}>⚠ {error}</div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Input */}
                    <div style={{ padding:'10px 12px', borderTop:'1px solid var(--border)',
                        display:'flex', gap:8, alignItems:'flex-end', flexShrink:0 }}>
                        <textarea ref={inputRef} value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKey}
                            placeholder="Ask about your crop…" rows={1} disabled={loading}
                            style={{ flex:1, resize:'none', overflow:'hidden',
                                background:'var(--bg-secondary)', border:'1px solid var(--border)',
                                borderRadius:9, padding:'8px 11px', fontSize:13,
                                color:'var(--text-primary)', fontFamily:'inherit', lineHeight:1.4, outline:'none' }}
                            onInput={e => {
                                e.target.style.height='auto';
                                e.target.style.height=Math.min(e.target.scrollHeight,96)+'px';
                            }} />
                        <button onClick={() => send()} disabled={!input.trim() || loading} style={{
                            width:34, height:34, borderRadius:9, border:'none',
                            background: input.trim() && !loading ? 'var(--green-600)' : 'var(--border)',
                            display:'flex', alignItems:'center', justifyContent:'center',
                            cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                            transition:'background .15s', flexShrink:0,
                        }}>
                            <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                                <path d="M2 8h12M9 4l5 4-5 4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}

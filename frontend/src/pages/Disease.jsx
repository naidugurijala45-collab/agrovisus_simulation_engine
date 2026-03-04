import { AlertTriangle, Loader2, Upload } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { predictDisease } from '../api/client';

function SeverityBadge({ severity }) {
    if (severity === 'None') return <span className="badge badge-green">Healthy</span>;
    if (severity === 'Mild') return <span className="badge badge-amber">Mild</span>;
    if (severity === 'Moderate') return <span className="badge badge-amber">Moderate</span>;
    return <span className="badge badge-red">Severe</span>;
}

export default function Disease() {
    const [preview, setPreview] = useState(null);
    const [file, setFile] = useState(null);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const onDrop = useCallback((accepted) => {
        const f = accepted[0];
        if (!f) return;
        setFile(f);
        setResult(null);
        setError(null);
        setPreview(URL.createObjectURL(f));
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'image/*': ['.jpg', '.jpeg', '.png', '.webp'] },
        maxFiles: 1,
    });

    const handleAnalyze = async () => {
        if (!file) return;
        setLoading(true);
        setError(null);
        try {
            const fd = new FormData();
            fd.append('file', file);
            const data = await predictDisease(fd);
            setResult(data);
        } catch (e) {
            setError(e.response?.data?.detail || e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <div className="page-header">
                <h2>🦠 Disease Diagnostics</h2>
                <p>Upload a leaf photo to get an instant AI-powered diagnosis and treatment recommendation.</p>
            </div>

            <div className="card-grid card-grid-2">
                {/* Upload Zone */}
                <div>
                    <div {...getRootProps()} className={`dropzone${isDragActive ? ' active' : ''}`}>
                        <input {...getInputProps()} />
                        {preview ? (
                            <img src={preview} alt="leaf preview" style={{ maxHeight: 240, borderRadius: 8, objectFit: 'cover' }} />
                        ) : (
                            <div>
                                <Upload size={40} style={{ margin: '0 auto 12px', color: 'var(--text-muted)' }} />
                                <p style={{ marginBottom: 4 }}>Drag & drop a leaf image here</p>
                                <p className="text-sm text-muted">or click to browse — JPG, PNG, WEBP</p>
                            </div>
                        )}
                    </div>

                    {file && (
                        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
                            <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading} style={{ flex: 1 }}>
                                {loading ? <Loader2 size={16} className="spinning" /> : <AlertTriangle size={16} />}
                                {loading ? 'Analysing…' : 'Analyse Disease'}
                            </button>
                            <button className="btn btn-outline" onClick={() => { setFile(null); setPreview(null); setResult(null); }}>
                                Clear
                            </button>
                        </div>
                    )}
                </div>

                {/* Results */}
                <div>
                    {!result && !loading && (
                        <div className="card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12, color: 'var(--text-muted)' }}>
                            <span style={{ fontSize: '3rem' }}>🔬</span>
                            <p>Upload an image to see the diagnosis here.</p>
                        </div>
                    )}

                    {loading && (
                        <div className="spinner-wrap">
                            <div className="spinner" />
                            <p className="text-muted">Running diagnosis model…</p>
                        </div>
                    )}

                    {error && (
                        <div className="card" style={{ borderColor: 'var(--red-400)', color: 'var(--red-400)' }}>
                            ⚠ {error}
                        </div>
                    )}

                    {result && (
                        <div className="card">
                            {/* Top result */}
                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
                                <div>
                                    <div className="stat-label">Primary Diagnosis</div>
                                    <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 }}>
                                        {result.top_prediction}
                                    </div>
                                </div>
                                <SeverityBadge severity={result.severity} />
                            </div>

                            {/* Confidence */}
                            <div className="form-group mb-4">
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                    <span className="form-label">Confidence</span>
                                    <span className="text-green text-sm">{(result.confidence * 100).toFixed(0)}%</span>
                                </div>
                                <div className="confidence-bar-track">
                                    <div className="confidence-bar-fill" style={{ width: `${result.confidence * 100}%` }} />
                                </div>
                            </div>

                            {/* Recommendation */}
                            <div style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: '14px 16px', marginBottom: 16, borderLeft: '3px solid var(--green-500)' }}>
                                <div className="form-label mb-4">📋 Recommendation</div>
                                <p className="text-sm" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{result.recommendation}</p>
                            </div>

                            {/* Other candidates */}
                            <div className="form-label mb-4">Other Candidates</div>
                            {result.candidates?.slice(1).map((c) => (
                                <div key={c.disease} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                                    <span className="text-sm text-muted">{c.disease}</span>
                                    <span className="text-sm text-muted">{(c.confidence * 100).toFixed(0)}%</span>
                                </div>
                            ))}

                            {result.action_required && (
                                <div style={{ marginTop: 16, padding: '10px 14px', borderRadius: 8, background: 'var(--red-glow)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--red-400)', fontSize: '0.85rem', display: 'flex', gap: 8 }}>
                                    <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                                    Immediate action required — treat within 48 hours.
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <style>{`.spinning { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

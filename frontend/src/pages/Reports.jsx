export default function Reports() {
    return (
        <div>
            <div className="page-header">
                <h2>📊 Reports</h2>
                <p>View and export agronomic simulation reports.</p>
            </div>
            <div className="card" style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: 16 }}>📑</div>
                <h3 style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>Report History</h3>
                <p className="text-sm">Run a simulation to generate your first report.</p>
                <p className="text-sm mt-4">Reports with CSV/PDF export will appear here — coming next sprint.</p>
            </div>
        </div>
    );
}

import { SearchBox } from '@mapbox/search-js-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useRef } from 'react';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';

const TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

// Fix Vite missing marker assets
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

/** Flies the map whenever the target position changes. */
function FlyToLocation({ lat, lng }) {
    const map = useMap();
    const prev = useRef(null);
    useEffect(() => {
        const key = `${lat},${lng}`;
        if (prev.current && prev.current !== key) {
            map.flyTo([lat, lng], 13, { duration: 1.2 });
        }
        prev.current = key;
    }, [lat, lng, map]);
    return null;
}

/** Handles pin-drop on map click. */
function MapClickHandler({ onChange }) {
    useMapEvents({
        click(e) {
            onChange(
                Number(e.latlng.lat.toFixed(4)),
                Number(e.latlng.lng.toFixed(4)),
                {}
            );
        },
    });
    return null;
}

/**
 * LocationPicker
 *
 * Props:
 *   lat, lng   — current position
 *   onChange(lat, lng, meta) — meta: { state_code, formatted_address }
 *   resolved   — { formatted_address, state_code } for info strip display
 */
export default function LocationPicker({ lat, lng, onChange, resolved }) {
    function handleRetrieve(res) {
        const feature = res?.features?.[0];
        if (!feature) return;

        const [fLng, fLat] = feature.geometry.coordinates;
        const ctx = feature.properties?.context ?? {};

        // region_code gives "IL" directly; region_code_full gives "US-IL" (needs stripping).
        // Prefer region_code to avoid picking up postal codes or other unexpected values.
        let state_code = ctx.region?.region_code ?? '';
        if (!state_code && ctx.region?.region_code_full) {
            state_code = ctx.region.region_code_full.replace(/^[A-Z]{2}-/, '');
        }
        // Guard: discard anything that isn't exactly 2 alpha characters
        if (!/^[A-Z]{2}$/.test(state_code)) state_code = '';

        const formatted_address =
            feature.properties?.full_address ??
            feature.properties?.place_formatted ??
            feature.properties?.name ??
            '';

        onChange(
            Number(fLat.toFixed(4)),
            Number(fLng.toFixed(4)),
            { state_code, formatted_address }
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {/* ── Search bar ── */}
            {TOKEN && (
                <div style={{ position: 'relative', zIndex: 1000 }}>
                    <SearchBox
                        accessToken={TOKEN}
                        onRetrieve={handleRetrieve}
                        placeholder="Search address or farm location…"
                        theme={{
                            variables: {
                                fontFamily: 'Inter, sans-serif',
                                fontWeightBold: '600',
                                colorBackground: '#0a0f0d',
                                colorBackgroundHover: '#141e17',
                                colorBackgroundActive: '#141e17',
                                colorText: '#f0fdf4',
                                colorTextSecondary: '#86efac',
                                colorPrimary: '#4ade80',
                                colorSecondary: '#22c55e',
                                border: '1px solid #1f3028',
                                borderRadius: '8px',
                                boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
                                unitSpacing: '4px',
                            },
                        }}
                    />
                    {/* Force light text on the shadow-DOM input — CSS vars pierce shadow boundaries */}
                    <style>{`
                        mapbox-search-box,
                        mapbox-search-box * {
                            --color-text: #f0fdf4 !important;
                            --color-background: #0a0f0d !important;
                            --color-background-hover: #141e17 !important;
                        }
                        mapbox-search-box input,
                        mapbox-search-box textarea {
                            color: #f0fdf4 !important;
                            background: #0a0f0d !important;
                            caret-color: #4ade80 !important;
                        }
                        .mbx-input,
                        .mapboxgl-ctrl-geocoder input,
                        [class*="SearchBox"] input,
                        [class*="search-box"] input {
                            color: #f0fdf4 !important;
                            background: #0a0f0d !important;
                            caret-color: #4ade80 !important;
                        }
                    `}</style>
                </div>
            )}

            {/* ── Resolved address info strip ── */}
            {resolved?.formatted_address && (
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    flexWrap: 'wrap', gap: 8,
                    padding: '8px 12px',
                    background: 'rgba(74,222,128,0.05)',
                    border: '1px solid rgba(74,222,128,0.15)',
                    borderRadius: 8,
                    fontSize: '0.78rem',
                }}>
                    <span style={{ color: 'var(--text-secondary)' }}>
                        📍 {resolved.formatted_address}
                    </span>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {resolved.state_code && (
                            <span style={{
                                background: 'var(--green-glow)', color: 'var(--green-400)',
                                border: '1px solid rgba(74,222,128,0.25)',
                                borderRadius: 999, padding: '2px 10px',
                                fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.5px',
                            }}>
                                {resolved.state_code}
                            </span>
                        )}
                        <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                            {lat.toFixed(4)}, {lng.toFixed(4)}
                        </span>
                    </div>
                </div>
            )}

            {/* ── Map ── */}
            <div style={{ height: 260, width: '100%', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)', zIndex: 0 }}>
                <MapContainer center={[lat, lng]} zoom={5} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    />
                    <Marker position={[lat, lng]} />
                    <MapClickHandler onChange={onChange} />
                    <FlyToLocation lat={lat} lng={lng} />
                </MapContainer>
            </div>
        </div>
    );
}

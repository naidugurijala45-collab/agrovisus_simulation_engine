import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';

// Fix for default marker icons in Vite avoiding missing local assets
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

function MapEvents({ onChange }) {
    useMapEvents({
        click(e) {
            onChange(Number(e.latlng.lat.toFixed(4)), Number(e.latlng.lng.toFixed(4)));
        },
    });
    return null;
}

export default function LocationPicker({ lat, lng, onChange }) {
    return (
        <div style={{ height: 260, width: '100%', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)', zIndex: 0 }}>
            <MapContainer center={[lat, lng]} zoom={5} style={{ height: '100%', width: '100%' }}>
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                <Marker position={[lat, lng]} />
                <MapEvents onChange={onChange} />
            </MapContainer>
        </div>
    );
}

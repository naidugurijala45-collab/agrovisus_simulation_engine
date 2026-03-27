import axios from 'axios';

// Local dev: Vite proxies /api → localhost:8001 (see vite.config.js)
// Production: set VITE_API_URL=https://your-backend.onrender.com/api in Vercel env vars
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL ?? '/api',
    timeout: 120000,
});

export const runSimulation = (payload, config = {}) =>
    api.post('/simulation/run', payload, config).then((r) => r.data);

export const getCropTemplates = () =>
    api.get('/crops/templates').then((r) => r.data);

export const predictDisease = (formData) =>
    api.post('/disease/predict', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);

export const healthCheck = () =>
    api.get('/health').then((r) => r.data);

export const askCropDoctor = (message, field_context) =>
    api.post('/chat', { message, field_context }).then((r) => r.data);

export default api;

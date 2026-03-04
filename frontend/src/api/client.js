import axios from 'axios';

// All /api calls are proxied by Vite to the FastAPI backend
// No absolute URL needed — avoids CORS issues entirely
const api = axios.create({
    baseURL: '/api',
    timeout: 120000,
});

export const runSimulation = (payload) =>
    api.post('/simulation/run', payload).then((r) => r.data);

export const getCropTemplates = () =>
    api.get('/crops/templates').then((r) => r.data);

export const predictDisease = (formData) =>
    api.post('/disease/predict', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);

export const healthCheck = () =>
    api.get('/health').then((r) => r.data);

export default api;

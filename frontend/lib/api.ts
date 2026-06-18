
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});

api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;

export async function login(email: string, password: string) {
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', password);
  const { data } = await api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  localStorage.setItem('token', data.access_token);
  return data;
}

export async function register(email: string, password: string) {
  const { data } = await api.post('/auth/register', { email, password });
  return data;
}

export async function getSignals(params: Record<string, any> = {}) {
  const { data } = await api.get('/signals/', { params });
  return data;
}

export async function getSignalStats() {
  const { data } = await api.get('/signals/stats');
  return data;
}

export async function createCheckout(tier: string, successUrl: string, cancelUrl: string) {
  const { data } = await api.post('/billing/checkout', { tier, success_url: successUrl, cancel_url: cancelUrl });
  return data;
}

export async function getSubscription() {
  const { data } = await api.get('/billing/subscription');
  return data;
}

export async function sendAlert(payload: { channel: string; signal_ids: string[]; subscription_id: string }) {
  const { data } = await api.post('/alerts/send', payload);
  return data;
}

export async function sendDigest() {
  const { data } = await api.post('/alerts/digest');
  return data;
}

export async function getSignalTrends(horizon: number = 7, bucketDays: number = 1) {
  const { data } = await api.get('/forecast/signal-trends', {
    params: { horizon_days: horizon, bucket_days: bucketDays },
  });
  return data;
}

export async function getTimesFMTrends(records: any[], horizon: number = 7, bucketDays: number = 1) {
  const timesfmUrl = process.env.NEXT_PUBLIC_TIMESFM_URL || 'http://127.0.0.1:8001';
  const { data } = await axios.post(`${timesfmUrl}/forecast/signal-trends`, {
    records,
    horizon_days: horizon,
    bucket_days: bucketDays,
  });
  return data;
}

export async function getTopOpportunities(params: Record<string, any> = {}) {
  const { data } = await api.get('/screen/top', { params });
  return data;
}

export async function getTimesFMForecast(series: number[], horizon: number = 7) {
  const timesfmUrl = process.env.NEXT_PUBLIC_TIMESFM_URL || 'http://127.0.0.1:8001';
  const { data } = await axios.post(`${timesfmUrl}/forecast`, {
    series,
    horizon,
    return_quantiles: true,
  });
  return data;
}

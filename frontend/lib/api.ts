
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

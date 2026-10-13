// The one place the frontend talks to the backend. Every call matches an operation in openapi.yaml.

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function errorMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  return `Request failed (${status})`;
}

async function request(path, { method = 'GET', body, params } = {}) {
  const query = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null)).toString();
  const response = await fetch(`${BASE_URL}${path}${query ? `?${query}` : ''}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(data, response.status));
  return data;
}

export const api = {
  listFamilies: () => request('/families'),
  createFamily: (name, startDate) =>
    request('/families', { method: 'POST', body: { name, start_date: startDate || undefined } }),
  joinFamily: (inviteCode, name) =>
    request('/families/join', { method: 'POST', body: { invite_code: inviteCode, name } }),
  getFamily: (familyId) => request(`/families/${familyId}`),
  listMembers: (familyId) => request(`/families/${familyId}/members`),
  memberSteps: (memberId, from, to) => request(`/members/${memberId}/steps`, { params: { from, to } }),
  logSteps: (memberId, entries, source = 'manual') =>
    request('/steps', { method: 'POST', body: { member_id: memberId, source, entries } }),
  weeklyLeaderboard: (familyId, asOf) =>
    request(`/families/${familyId}/leaderboards/weekly`, { params: { as_of: asOf } }),
  allTimeLeaderboard: (familyId, asOf) =>
    request(`/families/${familyId}/leaderboards/all-time`, { params: { as_of: asOf } }),
  listMessages: (familyId) => request(`/families/${familyId}/messages`),
  sendDigest: (familyId, kind, asOf) =>
    request(`/families/${familyId}/digests`, { method: 'POST', body: { kind, as_of: asOf } }),
};

/** Today's date in Eastern time as YYYY-MM-DD, matching the backend's day boundary. */
export function todayEastern(now = new Date()) {
  return now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
}

// The one place the frontend talks to the backend. Every call matches an operation in openapi.yaml.
//
// A family's invite code is its password: every request about a family sends it in the X-Family-Code header.
// This file keeps the codes this browser knows, the "code book", in localStorage: one entry per family, saved
// when you create, join or open a family with its code, or make a new code.

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';
const CODES_KEY = 'stepboard.codes'; // { [familyId]: { code, name } }
export const DEMO_CODE = 'DEMO';

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

// --- The code book ---------------------------------------------------------------------------------

function readCodes() {
  try {
    return JSON.parse(localStorage.getItem(CODES_KEY)) ?? {};
  } catch {
    return {};
  }
}

function writeCodes(codes) {
  try {
    localStorage.setItem(CODES_KEY, JSON.stringify(codes));
  } catch {
    // Storage unavailable: the codes last until the page is reloaded.
  }
}

const normalize = (code) => code.trim().toUpperCase();

function rememberFamily(family, code) {
  writeCodes({ ...readCodes(), [family.id]: { code: normalize(code), name: family.name } });
}

/** Families this browser has a code for, as [{ id, name, code }]. */
export function knownFamilies() {
  return Object.entries(readCodes()).map(([id, entry]) => ({ id: Number(id), ...entry }));
}

/** Drops a family whose code no longer works (someone made a new one). */
export function forgetFamily(familyId) {
  const { [familyId]: _, ...rest } = readCodes();
  writeCodes(rest);
}

const codeFor = (familyId) => readCodes()[familyId]?.code;

// --- Requests --------------------------------------------------------------------------------------

async function request(path, { method = 'GET', body, params, code } = {}) {
  const query = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v != null)).toString();
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (code) headers['X-Family-Code'] = code;
  const response = await fetch(`${BASE_URL}${path}${query ? `?${query}` : ''}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(data, response.status));
  return data;
}

/** A request about one family, with that family's code. */
const forFamily = (familyId, path, options = {}) => request(path, { ...options, code: codeFor(familyId) });

export const api = {
  /** The family a code opens; remembered, so the rest of the app can use it. */
  findFamily: async (code) => {
    const family = await request('/family', { code: normalize(code) });
    rememberFamily(family, code);
    return family;
  },
  createFamily: async (name, startDate) => {
    const family = await request('/families', { method: 'POST', body: { name, start_date: startDate || undefined } });
    rememberFamily(family, family.invite_code);
    return family;
  },
  joinFamily: async (inviteCode, name) => {
    const member = await request('/families/join', { method: 'POST', body: { invite_code: inviteCode, name } });
    await api.findFamily(inviteCode); // remembers the family's name and code
    return member;
  },
  /** Replaces the family's code; the old one stops working for everyone. Returns the family with its new code. */
  newInviteCode: async (familyId) => {
    const family = await forFamily(familyId, `/families/${familyId}/invite-code`, { method: 'POST', body: {} });
    rememberFamily(family, family.invite_code);
    return family;
  },
  getFamily: (familyId) => forFamily(familyId, `/families/${familyId}`),
  listMembers: (familyId) => forFamily(familyId, `/families/${familyId}/members`),
  memberSteps: (member, from, to) => forFamily(member.family_id, `/members/${member.id}/steps`, { params: { from, to } }),
  logSteps: (member, entries, source = 'manual') =>
    forFamily(member.family_id, '/steps', { method: 'POST', body: { member_id: member.id, source, entries } }),
  weeklyLeaderboard: (familyId, asOf) =>
    forFamily(familyId, `/families/${familyId}/leaderboards/weekly`, { params: { as_of: asOf } }),
  allTimeLeaderboard: (familyId, asOf) =>
    forFamily(familyId, `/families/${familyId}/leaderboards/all-time`, { params: { as_of: asOf } }),
  listMessages: (familyId) => forFamily(familyId, `/families/${familyId}/messages`),
  sendDigest: (familyId, kind, asOf) =>
    forFamily(familyId, `/families/${familyId}/digests`, { method: 'POST', body: { kind, as_of: asOf } }),
  /** This browser's code for a family, to show and share. */
  codeFor,
};

/** Today's date in Eastern time as YYYY-MM-DD, matching the backend's day boundary. */
export function todayEastern(now = new Date()) {
  return now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
}

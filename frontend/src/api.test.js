import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, forgetFamily, knownFamilies, todayEastern } from './api.js';

function mockFetch(...responses) {
  const queue = responses.map(([status, body]) => ({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }));
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(queue.length > 1 ? queue.shift() : queue[0]));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

const SPENCERS = { id: 7, name: 'Spencers', start_date: '2026-10-01' };
const CHRIS = { id: 3, family_id: 7, name: 'Chris' };
const codeSent = (fetch, call = 0) => fetch.mock.calls[call][1].headers['X-Family-Code'];

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('sends step entries as JSON to /api/steps, with the member’s family code', async () => {
    localStorage.setItem('stepboard.codes', JSON.stringify({ 7: { code: 'SPEN23', name: 'Spencers' } }));
    const fetch = mockFetch([200, []]);
    await api.logSteps(CHRIS, [{ day: '2026-10-12', steps: 9000 }]);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/steps');
    expect(options.method).toBe('POST');
    expect(codeSent(fetch)).toBe('SPEN23');
    expect(JSON.parse(options.body)).toEqual({
      member_id: 3,
      source: 'manual',
      entries: [{ day: '2026-10-12', steps: 9000 }],
    });
  });

  it('adds query parameters and skips empty ones', async () => {
    const fetch = mockFetch([200, {}]);
    await api.weeklyLeaderboard(1, '2026-10-11');
    await api.allTimeLeaderboard(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/families/1/leaderboards/weekly?as_of=2026-10-11');
    expect(fetch.mock.calls[1][0]).toBe('/api/families/1/leaderboards/all-time');
  });

  it('turns error responses into ApiError with the detail message', async () => {
    mockFetch([404, { detail: 'No family has that invite code' }]);
    await expect(api.joinFamily('NOPE', 'Sam')).rejects.toEqual(new ApiError(404, 'No family has that invite code'));
  });

  it('joins validation messages', async () => {
    mockFetch([422, { detail: [{ msg: 'too big' }, { msg: 'too small' }] }]);
    await expect(api.logSteps(CHRIS, [])).rejects.toThrow('too big; too small');
  });
});

describe('the code book: a family’s code is its password', () => {
  it('opening a family with its code remembers it, in capitals', async () => {
    const fetch = mockFetch([200, SPENCERS]);
    await api.findFamily(' spen23 ');
    expect(fetch.mock.calls[0][0]).toBe('/api/family');
    expect(codeSent(fetch)).toBe('SPEN23');
    expect(knownFamilies()).toEqual([{ id: 7, name: 'Spencers', code: 'SPEN23' }]);
  });

  it('creating a family remembers its new code', async () => {
    mockFetch([201, { ...SPENCERS, invite_code: 'SPEN23' }]);
    await api.createFamily('Spencers');
    expect(knownFamilies()).toEqual([{ id: 7, name: 'Spencers', code: 'SPEN23' }]);
  });

  it('joining remembers the family, by its name and code', async () => {
    const fetch = mockFetch([201, CHRIS], [200, SPENCERS]);
    expect(await api.joinFamily('spen23', 'Chris')).toEqual(CHRIS);
    expect(fetch.mock.calls[1][0]).toBe('/api/family');
    expect(knownFamilies()).toEqual([{ id: 7, name: 'Spencers', code: 'SPEN23' }]);
  });

  it('every request about a family sends that family’s code, and only that one', async () => {
    localStorage.setItem(
      'stepboard.codes',
      JSON.stringify({ 1: { code: 'DEMO', name: 'Demo Family' }, 7: { code: 'SPEN23', name: 'Spencers' } }),
    );
    const fetch = mockFetch([200, []]);
    await api.listMembers(7);
    await api.listMessages(1);
    await api.memberSteps(CHRIS);
    await api.sendDigest(7, 'weekly');
    expect([0, 1, 2, 3].map((i) => codeSent(fetch, i))).toEqual(['SPEN23', 'DEMO', 'SPEN23', 'SPEN23']);
  });

  it('a family with no code known is asked about without one, and the backend says what’s needed', async () => {
    const fetch = mockFetch([401, { detail: "This needs the family's invite code, in the X-Family-Code header" }]);
    await expect(api.getFamily(9)).rejects.toThrow("This needs the family's invite code");
    expect(codeSent(fetch)).toBeUndefined();
  });

  it('a new invite code replaces the old one in the code book', async () => {
    localStorage.setItem('stepboard.codes', JSON.stringify({ 7: { code: 'SPEN23', name: 'Spencers' } }));
    const fetch = mockFetch([200, { ...SPENCERS, invite_code: 'NEWC2D' }], [200, []]);
    await api.newInviteCode(7);
    expect(fetch.mock.calls[0][0]).toBe('/api/families/7/invite-code');
    expect(codeSent(fetch)).toBe('SPEN23'); // asked with the old code
    await api.listMembers(7);
    expect(codeSent(fetch, 1)).toBe('NEWC2D'); // everything after uses the new one
  });

  it('forgets a family', () => {
    localStorage.setItem('stepboard.codes', JSON.stringify({ 7: { code: 'SPEN23', name: 'Spencers' } }));
    forgetFamily(7);
    expect(knownFamilies()).toEqual([]);
  });

  it('there is no call that lists every family', () => {
    expect(api.listFamilies).toBeUndefined();
  });
});

describe('todayEastern', () => {
  it('uses the Eastern date, not UTC', () => {
    // 2:30 AM UTC on Oct 13 is still Oct 12 in New York.
    expect(todayEastern(new Date('2026-10-13T02:30:00Z'))).toBe('2026-10-12');
  });
});

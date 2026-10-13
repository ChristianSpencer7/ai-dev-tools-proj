import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, todayEastern } from './api.js';

function mockFetch(status, body) {
  const fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('sends step entries as JSON to /api/steps', async () => {
    const fetch = mockFetch(200, []);
    await api.logSteps(3, [{ day: '2026-10-12', steps: 9000 }]);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/steps');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      member_id: 3,
      source: 'manual',
      entries: [{ day: '2026-10-12', steps: 9000 }],
    });
  });

  it('adds query parameters and skips empty ones', async () => {
    const fetch = mockFetch(200, {});
    await api.weeklyLeaderboard(1, '2026-10-11');
    await api.allTimeLeaderboard(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/families/1/leaderboards/weekly?as_of=2026-10-11');
    expect(fetch.mock.calls[1][0]).toBe('/api/families/1/leaderboards/all-time');
  });

  it('turns error responses into ApiError with the detail message', async () => {
    mockFetch(404, { detail: 'No family has that invite code' });
    await expect(api.joinFamily('NOPE', 'Sam')).rejects.toEqual(
      new ApiError(404, 'No family has that invite code'),
    );
  });

  it('joins validation messages', async () => {
    mockFetch(422, { detail: [{ msg: 'too big' }, { msg: 'too small' }] });
    await expect(api.logSteps(1, [])).rejects.toThrow('too big; too small');
  });
});

describe('todayEastern', () => {
  it('uses the Eastern date, not UTC', () => {
    // 2:30 AM UTC on Oct 13 is still Oct 12 in New York.
    expect(todayEastern(new Date('2026-10-13T02:30:00Z'))).toBe('2026-10-12');
  });
});

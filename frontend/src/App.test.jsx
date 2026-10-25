import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App.jsx';

const DEMO = { id: 1, name: 'Demo Family', start_date: '2026-09-21' };
const BOARD = { kind: 'weekly', title: '📊 Week So Far — Oct 19–24', start: '2026-10-19', end: '2026-10-24',
  has_comparison: false, standings: [], callouts: [] };

/** A fake backend that knows the Demo Family's code and refuses any other, as one replaced by a family would be. */
function fakeBackend() {
  const fetch = vi.fn().mockImplementation((url, options) => {
    const code = options?.headers?.['X-Family-Code'];
    const reply = (status, body) => Promise.resolve({ ok: status < 300, status, json: () => Promise.resolve(body) });
    if (url === '/api/family') return code === 'DEMO' ? reply(200, DEMO) : reply(403, { detail: 'No family has that invite code' });
    if (url.startsWith('/api/families/1/') && code === 'DEMO') return reply(200, BOARD);
    return reply(403, { detail: "That invite code isn't this family's" });
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('App', () => {
  it('opens the Demo Family on a first visit, with its public code', async () => {
    const fetch = fakeBackend();
    render(<App />);
    expect(await screen.findByText(BOARD.title)).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Demo Family' })).toBeInTheDocument();
    expect(fetch.mock.calls.some(([url]) => url === '/api/families')).toBe(false); // there is no list to ask for
  });

  it('drops a family whose code someone replaced, and says what to do', async () => {
    localStorage.setItem('stepboard.codes', JSON.stringify({ 7: { code: 'SPEN23', name: 'Spencers' } }));
    localStorage.setItem('stepboard.family', '7');
    fakeBackend();
    render(<App />);
    expect(await screen.findByText(/The invite code for Spencers was changed/)).toBeInTheDocument();
    expect(await screen.findByText(BOARD.title)).toBeInTheDocument(); // back on the Demo Family
    expect(screen.queryByRole('option', { name: 'Spencers' })).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem('stepboard.codes'))).toEqual({ 1: { code: 'DEMO', name: 'Demo Family' } });
  });
});

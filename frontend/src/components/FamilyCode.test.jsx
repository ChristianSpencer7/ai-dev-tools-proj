import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api.js';
import FamilyCode from './FamilyCode.jsx';

const SPENCERS = { id: 7, name: 'Spencers', code: 'SPEN23' };

beforeEach(() => {
  localStorage.setItem(
    'stepboard.codes',
    JSON.stringify({ 1: { code: 'DEMO', name: 'Demo Family' }, 7: { code: 'SPEN23', name: 'Spencers' } }),
  );
});
afterEach(() => {
  cleanup(); // Testing Library only cleans up by itself when Vitest's globals are on
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('FamilyCode', () => {
  it('shows the code to share, and makes a new one only after asking', async () => {
    const newCode = vi.spyOn(api, 'newInviteCode').mockResolvedValue({ ...SPENCERS, invite_code: 'NEWC2D' });
    const onChanged = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<FamilyCode family={SPENCERS} onChanged={onChanged} />);

    expect(screen.getByText('SPEN23')).toBeInTheDocument();
    fireEvent.click(screen.getByText('New invite code'));
    expect(newCode).not.toHaveBeenCalled(); // said no

    fireEvent.click(screen.getByText('New invite code'));
    expect(await screen.findByText(/The new code is NEWC2D/)).toBeInTheDocument();
    expect(newCode).toHaveBeenCalledWith(7);
    expect(onChanged).toHaveBeenCalled();
  });

  it('offers no new code for the Demo Family, whose code is public', () => {
    render(<FamilyCode family={{ id: 1, name: 'Demo Family' }} />);
    expect(screen.getByText('DEMO')).toBeInTheDocument();
    expect(screen.queryByText('New invite code')).not.toBeInTheDocument();
  });
});

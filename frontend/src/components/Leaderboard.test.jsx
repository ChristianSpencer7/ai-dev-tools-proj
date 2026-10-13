import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { api } from '../api.js';
import Leaderboard from './Leaderboard.jsx';

const BOARD = {
  kind: 'weekly',
  title: '🏆 Weekly Steps — Oct 5–11',
  start: '2026-10-05',
  end: '2026-10-11',
  has_comparison: true,
  standings: [
    { member_id: 1, name: 'Dad', steps: 84210, rank: 1, medal: '🥇', prev_rank: 2, step_change: 6210 },
    { member_id: 4, name: 'Sam', steps: 52300, rank: 4, medal: null, prev_rank: null, step_change: null },
  ],
  callouts: [{ kind: 'best_single_day', text: '🔥 Best single day: Mom, 18,203 on Wednesday' }],
};

describe('Leaderboard', () => {
  it('shows medals, ranks, movement and callouts', async () => {
    vi.spyOn(api, 'weeklyLeaderboard').mockResolvedValue(BOARD);
    render(<Leaderboard familyId={1} />);

    expect(await screen.findByText(BOARD.title)).toBeInTheDocument();
    expect(screen.getByText('🥇')).toBeInTheDocument();
    expect(screen.getByText('4.')).toBeInTheDocument();
    expect(screen.getByText('▲ 1', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('new')).toBeInTheDocument();
    expect(screen.getByText(BOARD.callouts[0].text)).toBeInTheDocument();
    expect(api.weeklyLeaderboard).toHaveBeenCalledWith(1);
  });
});

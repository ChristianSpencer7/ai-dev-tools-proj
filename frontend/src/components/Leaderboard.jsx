import { useEffect, useState } from 'react';
import { api } from '../api.js';

function Change({ standing, hasComparison }) {
  if (!hasComparison) return null;
  if (standing.prev_rank == null) return <span className="change new">new</span>;
  const move = standing.prev_rank - standing.rank;
  const arrow = move > 0 ? `▲ ${move}` : move < 0 ? `▼ ${-move}` : '—';
  const steps = `${standing.step_change >= 0 ? '+' : ''}${standing.step_change.toLocaleString()}`;
  return (
    <span className={`change ${move > 0 ? 'up' : move < 0 ? 'down' : ''}`}>
      {arrow} <small>({steps} steps)</small>
    </span>
  );
}

export default function Leaderboard({ familyId, refreshKey = 0 }) {
  const [kind, setKind] = useState('weekly');
  const [board, setBoard] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = kind === 'weekly' ? api.weeklyLeaderboard : api.allTimeLeaderboard;
    setError(null);
    load(familyId)
      .then(setBoard)
      .catch((e) => setError(e.message));
  }, [familyId, kind, refreshKey]);

  return (
    <section>
      <div className="toggle">
        <button className={kind === 'weekly' ? 'active' : ''} onClick={() => setKind('weekly')}>
          This week
        </button>
        <button className={kind === 'all_time' ? 'active' : ''} onClick={() => setKind('all_time')}>
          All-time
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {board && (
        <>
          <h2>{board.title}</h2>
          {board.standings.length === 0 ? (
            <p>No one has joined yet.</p>
          ) : (
            <table className="board">
              <tbody>
                {board.standings.map((s) => (
                  <tr key={s.member_id}>
                    <td className="rank">{s.medal ?? `${s.rank}.`}</td>
                    <td>{s.name}</td>
                    <td className="steps">{s.steps.toLocaleString()}</td>
                    <td>
                      <Change standing={s} hasComparison={board.has_comparison} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {board.callouts.length > 0 && (
            <ul className="callouts">
              {board.callouts.map((c) => (
                <li key={c.kind}>{c.text}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

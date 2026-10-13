import { useCallback, useEffect, useState } from 'react';
import { api, todayEastern } from '../api.js';

export default function LogSteps({ member, onLogged }) {
  const today = todayEastern();
  const [day, setDay] = useState(today);
  const [steps, setSteps] = useState('');
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = useCallback(() => api.memberSteps(member.id).then(setHistory), [member.id]);

  useEffect(() => {
    loadHistory().catch(() => setHistory([]));
  }, [loadHistory]);

  const submit = async (event) => {
    event.preventDefault();
    try {
      await api.logSteps(member.id, [{ day, steps: Number(steps) }]);
      setStatus({ ok: true, text: `Saved ${Number(steps).toLocaleString()} steps for ${day}.` });
      setSteps('');
      await loadHistory();
      onLogged?.();
    } catch (e) {
      setStatus({ ok: false, text: e.message });
    }
  };

  return (
    <section>
      <h2>Log steps</h2>
      <p className="hint">Logging the same day again replaces that day's total.</p>
      <form onSubmit={submit} className="row">
        <label>
          Day <input type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} required />
        </label>
        <label>
          Steps{' '}
          <input
            type="number"
            min="0"
            max="100000"
            value={steps}
            onChange={(e) => setSteps(e.target.value)}
            required
          />
        </label>
        <button type="submit">Save</button>
      </form>
      {status && <p className={status.ok ? 'ok' : 'error'}>{status.text}</p>}

      <h3>Your last two weeks</h3>
      {history.length === 0 ? (
        <p>Nothing logged yet.</p>
      ) : (
        <table className="history">
          <tbody>
            {history.map((entry) => (
              <tr key={entry.day}>
                <td>{entry.day}</td>
                <td className="steps">{entry.steps.toLocaleString()}</td>
                <td className="hint">{entry.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

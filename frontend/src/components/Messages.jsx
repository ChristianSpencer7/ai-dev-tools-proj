import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

const DISCORD_LABEL = {
  not_configured: 'Shown here only (no Discord webhook set)',
  sent: 'Also posted to Discord',
  failed: 'Discord post failed',
};

export default function Messages({ familyId }) {
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(
    () =>
      api
        .listMessages(familyId)
        .then(setMessages)
        .catch((e) => setError(e.message)),
    [familyId],
  );

  useEffect(() => {
    load();
  }, [load]);

  const send = async (kind) => {
    setError(null);
    try {
      await api.sendDigest(familyId, kind);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section>
      <h2>Messages</h2>
      <p className="hint">
        Weekly digests go out Mondays at 8:00 AM Eastern, monthly digests on the 1st.
      </p>
      <div className="row">
        <button onClick={() => send('weekly')}>Send weekly digest now</button>
        <button onClick={() => send('monthly')}>Send monthly digest now</button>
      </div>
      {error && <p className="error">{error}</p>}
      {messages.length === 0 && <p>No messages yet.</p>}
      {messages.map((m) => (
        <article key={m.id} className="message">
          <header>
            <strong>{m.kind === 'weekly' ? 'Weekly digest' : 'Monthly digest'}</strong>{' '}
            <span className="hint">
              {new Date(m.created_at).toLocaleString()} · {DISCORD_LABEL[m.discord_status]}
            </span>
          </header>
          <pre>{m.text}</pre>
        </article>
      ))}
    </section>
  );
}

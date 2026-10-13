import { useCallback, useEffect, useState } from 'react';
import { api } from './api.js';
import JoinFamily from './components/JoinFamily.jsx';
import Leaderboard from './components/Leaderboard.jsx';
import LogSteps from './components/LogSteps.jsx';
import Messages from './components/Messages.jsx';

// Login is an open question in docs/plan.md; for now the browser remembers who you are.
function load(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable; the choice just won't survive a reload.
  }
}

const TABS = [
  ['leaderboard', 'Leaderboard'],
  ['log', 'Log steps'],
  ['messages', 'Messages'],
  ['join', 'Join or create'],
];

export default function App() {
  const [families, setFamilies] = useState([]);
  const [familyId, setFamilyId] = useState(() => load('stepboard.family'));
  const [me, setMe] = useState(() => load('stepboard.me')); // { id, family_id, name }
  const [tab, setTab] = useState('leaderboard');
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refreshFamilies = useCallback(
    () =>
      api
        .listFamilies()
        .then((list) => {
          setFamilies(list);
          setFamilyId((current) => (list.some((f) => f.id === current) ? current : list[0]?.id ?? null));
        })
        .catch((e) => setError(e.message)),
    [],
  );

  useEffect(() => {
    refreshFamilies();
  }, [refreshFamilies]);

  useEffect(() => save('stepboard.family', familyId), [familyId]);

  const onJoined = (member) => {
    setMe(member);
    save('stepboard.me', member);
    refreshFamilies().then(() => setFamilyId(member.family_id));
    setTab('log');
  };

  const myMember = me && me.family_id === familyId ? me : null;

  return (
    <div className="app">
      <header>
        <h1>👟 Family Step Leaderboard</h1>
        {families.length > 0 && (
          <label className="family-picker">
            Family{' '}
            <select value={familyId ?? ''} onChange={(e) => setFamilyId(Number(e.target.value))}>
              {families.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="whoami">{myMember ? `Logged in as ${myMember.name}` : 'Viewing as a guest'}</p>
      </header>

      <nav>
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </nav>

      {error && <p className="error">Couldn't reach the backend: {error}</p>}

      <main>
        {tab === 'leaderboard' && familyId && <Leaderboard familyId={familyId} refreshKey={refreshKey} />}
        {tab === 'log' &&
          (myMember ? (
            <LogSteps member={myMember} onLogged={() => setRefreshKey((k) => k + 1)} />
          ) : (
            <p>
              Join this family first to log steps.{' '}
              <button className="link" onClick={() => setTab('join')}>
                Join or create a family
              </button>
            </p>
          ))}
        {tab === 'messages' && familyId && <Messages familyId={familyId} />}
        {tab === 'join' && <JoinFamily onJoined={onJoined} />}
        {!familyId && tab !== 'join' && <p>No families yet. Create one to get started.</p>}
      </main>
    </div>
  );
}

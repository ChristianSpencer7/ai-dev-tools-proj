import { useCallback, useEffect, useState } from 'react';
import { ApiError, DEMO_CODE, api, forgetFamily, knownFamilies } from './api.js';
import FamilyCode from './components/FamilyCode.jsx';
import JoinFamily from './components/JoinFamily.jsx';
import Leaderboard from './components/Leaderboard.jsx';
import LogSteps from './components/LogSteps.jsx';
import Messages from './components/Messages.jsx';

// There are no logins: a family's invite code is its password, and this browser keeps the codes it knows
// (api.js). It also remembers which family is showing and who you joined as.
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

/** Opens the Demo Family, and checks every code this browser has still works. Returns the families that dropped. */
async function checkCodes() {
  await api.findFamily(DEMO_CODE);
  const dropped = [];
  for (const family of knownFamilies()) {
    if (family.code === DEMO_CODE) continue;
    try {
      await api.findFamily(family.code);
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 403) throw e;
      forgetFamily(family.id); // someone in the family made a new code
      dropped.push(family.name);
    }
  }
  return dropped;
}

export default function App() {
  const [families, setFamilies] = useState(knownFamilies);
  const [familyId, setFamilyId] = useState(() => load('stepboard.family'));
  const [me, setMe] = useState(() => load('stepboard.me')); // { id, family_id, name }
  const [tab, setTab] = useState('leaderboard');
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refreshFamilies = useCallback(() => {
    const list = knownFamilies();
    setFamilies(list);
    setFamilyId((current) =>
      list.some((f) => f.id === current) ? current : (list.find((f) => f.code === DEMO_CODE) ?? list[0])?.id ?? null,
    );
  }, []);

  useEffect(() => {
    checkCodes()
      .then((dropped) => {
        if (dropped.length) {
          setNotice(
            `The invite code for ${dropped.join(' and ')} was changed. Ask your family for the new one, ` +
              'then open the family with it under "Join or create".',
          );
        }
        refreshFamilies();
      })
      .catch((e) => setError(e.message));
  }, [refreshFamilies]);

  useEffect(() => save('stepboard.family', familyId), [familyId]);

  const onJoined = (member) => {
    setMe(member);
    save('stepboard.me', member);
    refreshFamilies();
    setFamilyId(member.family_id);
    setTab('log');
  };

  const onFamilyAdded = (family, { stay = false } = {}) => {
    refreshFamilies();
    setFamilyId(family.id);
    if (!stay) setTab('leaderboard');
  };

  const current = families.find((f) => f.id === familyId) ?? null;
  const myMember = me && me.family_id === familyId && current ? me : null;

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
      {notice && <p className="error">{notice}</p>}

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
        {tab === 'join' && (
          <>
            {current && <FamilyCode family={current} onChanged={refreshFamilies} />}
            <JoinFamily onJoined={onJoined} onFamilyAdded={onFamilyAdded} />
          </>
        )}
        {!familyId && tab !== 'join' && <p>Loading the demo family…</p>}
      </main>
    </div>
  );
}

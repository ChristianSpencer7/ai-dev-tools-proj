import { useState } from 'react';
import { api } from '../api.js';

export default function JoinFamily({ onJoined }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('DEMO');
  const [familyName, setFamilyName] = useState('');
  const [created, setCreated] = useState(null);
  const [error, setError] = useState(null);

  const join = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      onJoined(await api.joinFamily(code, name));
    } catch (e) {
      setError(e.message);
    }
  };

  const create = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      const family = await api.createFamily(familyName);
      setCreated(family);
      setCode(family.invite_code);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section>
      <h2>Join a family</h2>
      <p className="hint">
        The demo family's invite code is <code>DEMO</code>.
      </p>
      <form onSubmit={join} className="row">
        <label>
          Invite code <input value={code} onChange={(e) => setCode(e.target.value)} required />
        </label>
        <label>
          Your name <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} required />
        </label>
        <button type="submit">Join</button>
      </form>

      <h2>Or create a new family</h2>
      <form onSubmit={create} className="row">
        <label>
          Family name{' '}
          <input value={familyName} onChange={(e) => setFamilyName(e.target.value)} maxLength={80} required />
        </label>
        <button type="submit">Create</button>
      </form>
      {created && (
        <p className="ok">
          Created {created.name}. Its invite code is <code>{created.invite_code}</code>, and it's filled in
          above, so enter your name and join.
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

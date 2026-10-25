import { useState } from 'react';
import { api } from '../api.js';

// A family's invite code is its password: joining, creating and opening a family all leave its code in this
// browser (api.js), and the family appears in the picker.
export default function JoinFamily({ onJoined, onFamilyAdded }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('DEMO');
  const [openCode, setOpenCode] = useState('');
  const [familyName, setFamilyName] = useState('');
  const [created, setCreated] = useState(null);
  const [error, setError] = useState(null);

  const attempt = (action) => async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e.message);
    }
  };

  const join = attempt(async () => onJoined(await api.joinFamily(code, name)));

  const open = attempt(async () => {
    const family = await api.findFamily(openCode);
    setOpenCode('');
    onFamilyAdded(family);
  });

  const create = attempt(async () => {
    const family = await api.createFamily(familyName);
    setCreated(family);
    setCode(family.invite_code);
    onFamilyAdded(family, { stay: true });
  });

  return (
    <section>
      <h2>Join a family</h2>
      <p className="hint">
        The demo family's invite code is <code>DEMO</code>. Anyone with a family's code can see and change its board,
        so share it only with your family.
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

      <h2>Already in a family?</h2>
      <p className="hint">On a new device, open your family with its code. You stay the same member.</p>
      <form onSubmit={open} className="row">
        <label>
          Invite code <input value={openCode} onChange={(e) => setOpenCode(e.target.value)} required />
        </label>
        <button type="submit">Open</button>
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
          Created {created.name}. Its invite code is <code>{created.invite_code}</code>: keep it, since it's how
          your family gets in. It's filled in above, so enter your name and join.
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

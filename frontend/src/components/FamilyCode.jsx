import { useState } from 'react';
import { DEMO_CODE, api } from '../api.js';

// The current family's invite code, to share, and a way to replace it when it has been shared too widely.
export default function FamilyCode({ family, onChanged }) {
  const [status, setStatus] = useState(null);
  const code = api.codeFor(family.id);
  if (!code) return null;

  if (code === DEMO_CODE) {
    return (
      <section>
        <h2>{family.name}'s invite code</h2>
        <p>
          <code>{DEMO_CODE}</code>. It's public, so it can't be changed.
        </p>
      </section>
    );
  }

  const replace = async () => {
    const sure = window.confirm(
      `Make a new invite code for ${family.name}? The current one stops working at once, for everyone. ` +
        'You will need to give the new one to the rest of your family.',
    );
    if (!sure) return;
    try {
      const updated = await api.newInviteCode(family.id);
      setStatus({ ok: true, text: `The new code is ${updated.invite_code}. Share it with your family: the old one no longer works.` });
      onChanged?.(updated);
    } catch (e) {
      setStatus({ ok: false, text: e.message });
    }
  };

  return (
    <section>
      <h2>{family.name}'s invite code</h2>
      <p>
        <code>{code}</code>. Anyone with it can see and change your family's board, so share it only with your family.
      </p>
      <button onClick={replace}>New invite code</button>
      {status && <p className={status.ok ? 'ok' : 'error'}>{status.text}</p>}
    </section>
  );
}

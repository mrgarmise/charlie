'use strict';
const form = document.querySelector('#setup');
const status = document.querySelector('#status');
const ticket = document.querySelector('#ticket');
let ticketURL;
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (location.protocol !== 'https:') { status.textContent = 'Verified HTTPS is required.'; return; }
  const token = document.querySelector('#token');
  const password = document.querySelector('#password');
  const ssid = document.querySelector('#ssid');
  const button = form.querySelector('button');
  button.disabled = true; ticket.hidden = true;
  if (ticketURL) { URL.revokeObjectURL(ticketURL); ticketURL = undefined; }
  try {
    const nameBytes = new TextEncoder().encode(ssid.value).length;
    const passwordBytes = new TextEncoder().encode(password.value).length;
    if (nameBytes < 1 || nameBytes > 32 || passwordBytes < 8 || passwordBytes > 63) throw new Error();
    const headers = {'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json'};
    const options = {headers, credentials: 'omit', cache: 'no-store', redirect: 'error'};
    const identityResponse = await fetch('/v1/network', {...options, signal: AbortSignal.timeout(5000)});
    const identity = await identityResponse.json();
    if (!identityResponse.ok || !/^elegoo-[a-f0-9]{12}$/.test(identity.device_id)) throw new Error();
    const transaction = Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('');
    const response = await fetch('/v1/network/prepare', {...options, method: 'POST',
      body: JSON.stringify({ssid: ssid.value, password: password.value, transaction, lease_seconds: 90}),
      signal: AbortSignal.timeout(5000)});
    const accepted = await response.json();
    if (!response.ok || accepted.accepted !== true || accepted.transaction !== transaction) throw new Error();
    const handoff = {version: 1, device_id: identity.device_id, transaction,
      ssid: ssid.value, lease_seconds: 90};
    ticketURL = URL.createObjectURL(new Blob([JSON.stringify(handoff)], {type: 'application/json'}));
    ticket.href = ticketURL; ticket.download = 'charlie-elegoo-verification.json'; ticket.hidden = false;
    status.textContent = 'Received, not yet saved. Save the ticket and explicitly authorize Charlie to verify the target LAN within 90 seconds.';
  } catch (_) {
    status.textContent = 'Receipt unverified. Association may move the AP channel; use authenticated Charlie status. Unconfirmed changes expire.';
  } finally {
    token.value = ''; password.value = ''; ssid.value = ''; button.disabled = false;
  }
});

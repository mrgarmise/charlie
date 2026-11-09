'use strict';
const form = document.querySelector('#setup');
const status = document.querySelector('#status');
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (location.protocol !== 'https:') {
    status.textContent = 'A physically verified HTTPS connection is required.';
    return;
  }
  const button = form.querySelector('button');
  button.disabled = true;
  const token = document.querySelector('#token');
  const password = document.querySelector('#password');
  const ssid = document.querySelector('#ssid');
  try {
    if (new TextEncoder().encode(ssid.value).length > 32 ||
        new TextEncoder().encode(password.value).length > 63) throw new Error();
    const transaction = Array.from(crypto.getRandomValues(new Uint8Array(16)),
      byte => byte.toString(16).padStart(2, '0')).join('');
    const response = await fetch('/v1/network/prepare', {
      method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error',
      headers: {'Authorization': 'Bearer ' + token.value, 'Content-Type': 'application/json'},
      body: JSON.stringify({ssid: ssid.value, password: password.value,
        transaction, lease_seconds: 90}), signal: AbortSignal.timeout(5000)
    });
    const reply = await response.json();
    if (!response.ok || reply.accepted !== true || reply.transaction !== transaction) throw new Error();
    status.textContent = 'Received. Target join and independent Charlie verification are still pending. Unconfirmed changes expire.';
  } catch (_) {
    status.textContent = 'Receipt unverified. The AP may change channel during association. Check Charlie status; recovery remains available.';
  } finally {
    token.value = ''; password.value = ''; ssid.value = ''; button.disabled = false;
  }
});

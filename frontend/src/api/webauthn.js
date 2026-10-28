// Browser <-> server glue for WebAuthn. The server sends/accepts base64url JSON.

export const passkeysSupported = () =>
  typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials

export function b64urlToBuffer(value) {
  const pad = '='.repeat((4 - (value.length % 4)) % 4)
  const raw = atob((value + pad).replace(/-/g, '+').replace(/_/g, '/'))
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes.buffer
}

export function bufferToB64url(buffer) {
  const bytes = new Uint8Array(buffer)
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function prepareCreationOptions(options) {
  return {
    ...options,
    challenge: b64urlToBuffer(options.challenge),
    user: { ...options.user, id: b64urlToBuffer(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((c) => ({ ...c, id: b64urlToBuffer(c.id) })),
  }
}

export function prepareRequestOptions(options) {
  return {
    ...options,
    challenge: b64urlToBuffer(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((c) => ({ ...c, id: b64urlToBuffer(c.id) })),
  }
}

export async function createCredential(options) {
  const cred = await navigator.credentials.create({ publicKey: prepareCreationOptions(options) })
  return {
    id: cred.id,
    rawId: bufferToB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufferToB64url(cred.response.clientDataJSON),
      attestationObject: bufferToB64url(cred.response.attestationObject),
      transports: cred.response.getTransports ? cred.response.getTransports() : [],
    },
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
  }
}

export async function getCredential(options) {
  const cred = await navigator.credentials.get({ publicKey: prepareRequestOptions(options) })
  const r = cred.response
  return {
    id: cred.id,
    rawId: bufferToB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufferToB64url(r.clientDataJSON),
      authenticatorData: bufferToB64url(r.authenticatorData),
      signature: bufferToB64url(r.signature),
      userHandle: r.userHandle ? bufferToB64url(r.userHandle) : null,
    },
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
  }
}

// Friendly text for the errors browsers throw when the user cancels or the device can't do it.
export function webauthnErrorMessage(e) {
  if (e?.name === 'NotAllowedError') return 'The passkey prompt was cancelled or timed out.'
  if (e?.name === 'InvalidStateError') return 'This passkey is already registered on this device.'
  if (e?.name === 'SecurityError') return 'Passkeys need https:// or http://localhost, and a matching WEBAUTHN_RP_ID.'
  return null
}

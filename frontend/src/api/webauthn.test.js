import { describe, expect, it } from 'vitest'
import { b64urlToBuffer, bufferToB64url, prepareCreationOptions, prepareRequestOptions } from './webauthn'

describe('base64url helpers', () => {
  it('round-trips arbitrary bytes, including url-unsafe characters', () => {
    const bytes = new Uint8Array([251, 255, 190, 0, 1, 2, 250])
    const text = bufferToB64url(bytes.buffer)
    expect(text).not.toMatch(/[+/=]/)
    expect([...new Uint8Array(b64urlToBuffer(text))]).toEqual([...bytes])
  })

  it('converts the binary fields of creation and request options', () => {
    const id = bufferToB64url(new Uint8Array([1, 2, 3]).buffer)
    const create = prepareCreationOptions({
      challenge: id, user: { id, name: 'a' }, excludeCredentials: [{ id, type: 'public-key' }],
    })
    expect(create.challenge).toBeInstanceOf(ArrayBuffer)
    expect(create.user.id).toBeInstanceOf(ArrayBuffer)
    expect(create.excludeCredentials[0].id).toBeInstanceOf(ArrayBuffer)

    const get = prepareRequestOptions({ challenge: id, allowCredentials: [{ id, type: 'public-key' }] })
    expect(get.allowCredentials[0].id).toBeInstanceOf(ArrayBuffer)
    expect(prepareRequestOptions({ challenge: id }).allowCredentials).toEqual([])
  })
})

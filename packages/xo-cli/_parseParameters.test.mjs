import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { parseParameters } from './_parseParameters.mjs'

describe('parseParameters()', () => {
  it('parses strings', () => {
    assert.deepEqual(parseParameters(['foo=bar', 'empty=', 'eq=a=b']), { foo: 'bar', empty: '', eq: 'a=b' })
  })

  it('parses true and false as booleans', () => {
    assert.deepEqual(parseParameters(['foo=true', 'bar=false']), { foo: true, bar: false })
  })

  it('parses JSON encoded values', () => {
    assert.deepEqual(parseParameters(['n=json:42', 'a=json:["x"]', 'b=json:true', 'z=json:null']), {
      n: 42,
      a: ['x'],
      b: true,
      z: null,
    })
  })

  it('keeps JSON encoded strings as strings', () => {
    assert.deepEqual(parseParameters(['foo=json:"true"', 'bar=json:"false"']), { foo: 'true', bar: 'false' })
  })

  it('does not convert the @ parameter', () => {
    assert.deepEqual(parseParameters(['@=true']), { '@': 'true' })
  })

  it('throws on invalid arguments', () => {
    assert.throws(() => parseParameters(['foo']), /invalid arg: foo/)
  })
})

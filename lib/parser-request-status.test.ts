// Run with: npx tsx --test lib/parser-request-status.test.ts
import test from 'node:test'
import assert from 'node:assert/strict'
import { toClientParserStatus, parserRequestLabel } from './parser-request-status'

test('new / in_progress / testing all collapse to Processing', () => {
  for (const s of ['new', 'in_progress', 'testing']) {
    assert.deepEqual(toClientParserStatus(s), { key: 'processing', label: 'Processing' })
  }
})

test('resolved is Ready', () => {
  assert.deepEqual(toClientParserStatus('resolved'), { key: 'ready', label: 'Ready' })
})

test('null / unknown never leak a raw internal label', () => {
  for (const s of [null, undefined, '', 'failed', 'Testing']) {
    assert.equal(toClientParserStatus(s as string | null).label, 'Processing')
  }
})

test('label falls back to deal name, then a generic label, never "Unnamed bank"', () => {
  assert.equal(parserRequestLabel({ bank_name: 'SBM Bank', deal_name: 'Buildex 2' }), 'SBM Bank')
  assert.equal(parserRequestLabel({ bank_name: null, deal_name: 'Buildex 2' }), 'Statement format for Buildex 2')
  assert.equal(parserRequestLabel({ bank_name: null, deal_name: null }), 'Statement format request')
})

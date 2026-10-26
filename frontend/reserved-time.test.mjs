import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compiled = ts.transpileModule(fs.readFileSync('src/lib/reserved-time.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const { mergeReservedTimes } = loaded.exports;
const range = (start, end) => ({ starts_at: `2026-10-26T${start}:00Z`, ends_at: `2026-10-26T${end}:00Z` });
test('merges adjacent reservations and chains of gaps shorter than thirty minutes', () => {
  const input = [range('11:15', '12:00'), range('09:00', '10:00'), range('10:00', '11:00')];
  assert.deepEqual(mergeReservedTimes(input, 30), [range('09:00', '12:00')]);
  assert.equal(input[0].starts_at, range('11:15', '12:00').starts_at);
});
test('preserves gaps of exactly thirty minutes or longer', () => {
  const input = [range('09:00', '10:00'), range('10:30', '11:00'), range('12:00', '13:00')];
  assert.deepEqual(mergeReservedTimes(input, 30), input);
});
test('nested and overlapping reservations keep the latest end', () => {
  assert.deepEqual(mergeReservedTimes([range('09:00', '11:00'), range('09:30', '10:00'), range('10:30', '12:00')], 30), [range('09:00', '12:00')]);
  assert.deepEqual(mergeReservedTimes([], 50), []);
});

test('a forty-minute gap is unavailable for fifty-minute sessions, but open for thirty-minute sessions', () => {
  const input = [range('11:00', '11:50'), range('12:30', '13:20')];
  assert.deepEqual(mergeReservedTimes(input, 50), [range('11:00', '13:20')]);
  assert.deepEqual(mergeReservedTimes(input, 30), input);
});
test('a gap equal to the selected session length remains open', () => {
  const input = [range('11:00', '11:50'), range('12:40', '13:30')];
  assert.deepEqual(mergeReservedTimes(input, 50), input);
});

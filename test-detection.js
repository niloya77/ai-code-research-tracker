/**
 * Manual test for detectLargeInsertion logic (no VS Code needed)
 */
const { detectLargeInsertion } = require('./out/insertionDetector');

function makeEvent(changes) {
  return {
    contentChanges: changes.map(c => ({
      text: c.text,
      range: {
        start: { line: c.startLine ?? 0 },
        end: { line: c.endLine ?? 0 }
      }
    }))
  };
}

let passed = 0;
let failed = 0;

function test(label, event, expectNull) {
  const result = detectLargeInsertion(event);
  const ok = expectNull ? result === null : result !== null;
  if (ok) {
    console.log(`  PASS  ${label}${result ? ` (${result.lineCount} line(s), startLine=${result.startLine})` : ''}`);
    passed++;
  } else {
    console.log(`  FAIL  ${label} — expected ${expectNull ? 'null' : 'a result'}, got ${JSON.stringify(result)}`);
    failed++;
  }
}

console.log('\n=== insertionDetector tests ===\n');

// Should NOT trigger
test('single keystroke (1 char)',         makeEvent([{ text: 'a' }]), true);
test('empty change',                      makeEvent([{ text: '' }]), true);
test('no changes',                        makeEvent([]), true);

// Should trigger
test('2 chars pasted (1 line)',           makeEvent([{ text: 'ab' }]), false);
test('short paste with newline',          makeEvent([{ text: 'foo\nbar' }]), false);
test('5-line paste',                      makeEvent([{ text: 'a\nb\nc\nd\ne' }]), false);
test('10-line paste',                     makeEvent([{ text: Array(10).fill('line').join('\n') }]), false);
test('single line of code pasted',       makeEvent([{ text: 'console.log("hello")' }]), false);
test('multi-change (split paste)',        makeEvent([
  { text: 'foo\n', startLine: 0 },
  { text: 'bar\nbaz', startLine: 5 }
]), false);

console.log(`\n${passed} passed, ${failed} failed\n`);
process.exit(failed > 0 ? 1 : 0);

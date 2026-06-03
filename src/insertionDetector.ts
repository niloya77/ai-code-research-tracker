import * as vscode from 'vscode';

export interface DetectedInsertion {
  startLine: number;
  endLine: number;
  lineCount: number;
  commentDensity: number;
}

// Minimum non-whitespace chars to distinguish real code from Enter/indent-only changes.
// Anything appearing in a single document-change event arrived faster than a human
// could type it, making it a strong paste / AI-insertion signal regardless of line count.
const MIN_NON_WHITESPACE_CHARS = 8;

// Lines whose trimmed content starts with a comment marker.
// LLMs consistently produce higher comment-to-code ratios than human authors,
// so comment density serves as a supplementary AI-origin indicator.
function calculateCommentDensity(text: string): number {
  const lines = text.split('\n');
  const nonEmpty = lines.filter(l => l.trim().length > 0);
  if (nonEmpty.length === 0) return 0;

  const commentCount = nonEmpty.filter(l => {
    const t = l.trim();
    return t.startsWith('//') ||
           t.startsWith('#')  ||
           t.startsWith('*')  ||
           t.startsWith('/*') ||
           t.startsWith('"""') ||
           t.startsWith("'''") ||
           t.startsWith('--');
  }).length;

  return commentCount / nonEmpty.length;
}

export function detectLargeInsertion(
  event: vscode.TextDocumentChangeEvent
): DetectedInsertion | null {
  for (const change of event.contentChanges) {
    if (change.text.length === 0) continue;

    const nonWhitespace = change.text.replace(/\s/g, '').length;
    if (nonWhitespace >= MIN_NON_WHITESPACE_CHARS) {
      const newlines = (change.text.match(/\n/g) ?? []).length;
      return {
        startLine: change.range.start.line,
        endLine: change.range.start.line + newlines,
        lineCount: newlines + 1,
        commentDensity: calculateCommentDensity(change.text)
      };
    }
  }

  return null;
}

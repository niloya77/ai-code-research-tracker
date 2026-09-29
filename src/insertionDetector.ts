import * as vscode from 'vscode';

export interface DetectedInsertion {
  startLine: number;
  endLine: number;
  lineCount: number;
}

// Minimum non-whitespace chars to distinguish real code from Enter/indent-only changes.
// Anything appearing in a single document-change event arrived faster than a human
// could type it, making it a strong paste / AI-insertion signal regardless of line count.
const MIN_NON_WHITESPACE_CHARS = 8;

export function detectLargeInsertion(
  event: vscode.TextDocumentChangeEvent
): DetectedInsertion | null {
  for (const change of event.contentChanges) {
    if (change.text.length === 0) continue;

    const nonWhitespace = change.text.replace(/\s/g, '').length;
    if (nonWhitespace >= MIN_NON_WHITESPACE_CHARS) {
      const newlines = (change.text.match(/\n/g) ?? []).length;
      const trailingNewline = change.text.endsWith('\n') ? 1 : 0;
      return {
        startLine: change.range.start.line,
        endLine: change.range.start.line + newlines - trailingNewline,
        lineCount: newlines - trailingNewline + 1,
      };
    }
  }

  return null;
}

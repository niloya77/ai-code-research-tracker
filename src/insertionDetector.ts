import * as vscode from 'vscode';

export interface DetectedInsertion {
  startLine: number;
  endLine: number;
  lineCount: number;
}

// Trigger on any paste with real code content — ignore Enter/space/indent-only changes
const MIN_NON_WHITESPACE_CHARS = 8;

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
        lineCount: newlines + 1
      };
    }
  }

  return null;
}

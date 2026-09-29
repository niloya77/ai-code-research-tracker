import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { InsertionRecord } from './types';

// Append-only log — unlike DataStore.save() (which overwrites the full snapshot),
// this file only ever grows, so a bug or a bad Supabase write can't erase history.
export class BackupStore {
  private filePath: string;

  constructor(context: vscode.ExtensionContext) {
    const storageDir = context.globalStorageUri.fsPath;
    if (!fs.existsSync(storageDir)) {
      fs.mkdirSync(storageDir, { recursive: true });
    }
    this.filePath = path.join(storageDir, 'insertion-records-backup.jsonl');
  }

  getPath(): string {
    return this.filePath;
  }

  append(record: InsertionRecord, participantId: string): void {
    try {
      const line = JSON.stringify({ backedUpAt: Date.now(), participantId, record });
      fs.appendFileSync(this.filePath, line + '\n', 'utf8');
    } catch (err) {
      console.error('[AITracker] Backup append failed:', err);
    }
  }
}

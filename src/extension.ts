import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { InsertionRecord } from './types';
import { detectLargeInsertion } from './insertionDetector';
import { BlockTracker } from './blockTracker';
import { DataStore } from './dataStore';
import { SupabaseClient } from './supabaseClient';
import { BackupStore } from './backupStore';
import { StatsPanel } from './statsPanel';

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

async function askParticipantId(context: vscode.ExtensionContext): Promise<string> {
  const stored = context.globalState.get<string>('participantId') ?? '';
  const input = await vscode.window.showInputBox({
    title: 'AI Code Research Tracker — Participant ID',
    prompt: 'Enter your participant ID (provided by the researcher)',
    placeHolder: 'e.g. P01',
    value: stored,
    ignoreFocusOut: true,
    validateInput: v => (v.trim().length === 0 ? 'Participant ID cannot be empty' : null)
  });
  if (input === undefined) {
    // User cancelled — keep the stored value (or 'unknown' if none set yet)
    return stored || 'unknown';
  }
  const id = input.trim() || 'unknown';
  await context.globalState.update('participantId', id);
  return id;
}

let tracker: BlockTracker;
let dataStore: DataStore;
let supabase: SupabaseClient;
let backupStore: BackupStore;
let participantId: string | null = null;
let statusBarItem: vscode.StatusBarItem;
let syncStatusItem: vscode.StatusBarItem;
let pendingRecordId: string | null = null;
let reviewTimerInterval: ReturnType<typeof setInterval> | null = null;
let saveTimer: ReturnType<typeof setTimeout> | null = null;
let retryInterval: ReturnType<typeof setInterval> | null = null;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  tracker = new BlockTracker();
  dataStore = new DataStore(context);
  supabase = new SupabaseClient();
  backupStore = new BackupStore(context);
  // Clear stale pendingConfirmation records from previous sessions — they can never be resolved
  const saved = dataStore.load().filter(r => !r.pendingConfirmation);
  const expiredOnLoad = tracker.loadAll(saved);

  participantId = await askParticipantId(context);

  // Sync any records whose 7-day observation window elapsed while the editor was closed
  if (expiredOnLoad.length > 0) {
    for (const record of expiredOnLoad) {
      syncToSupabase(record);
    }
    scheduleSave();
  }

  // Sync records that failed to reach Supabase while offline (lastSynced === null means never synced)
  const neverSynced = tracker.getAll().filter(r => r.lastSynced === null && r.condition !== null);
  for (const record of neverSynced) {
    syncToSupabase(record);
  }
  if (neverSynced.length > 0) {
    console.log(`[AITracker] Startup: retrying ${neverSynced.length} unsynced record(s).`);
    scheduleSave();
  }

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'aiTracker.acceptCode';

  syncStatusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 99);
  syncStatusItem.tooltip = 'AI Tracker: Supabase sync status';
  syncStatusItem.show();
  updateSyncStatus(true);

  context.subscriptions.push(statusBarItem, syncStatusItem);

  // Restore an in-progress review interrupted by a restart (e.g. user picked
  // "Yes, I'll review" but closed the editor before clicking Accept). Without this,
  // the record stays pendingAcceptance forever and never syncs to Supabase.
  const orphanedPending = tracker.getAll()
    .filter(r => r.pendingAcceptance)
    .sort((a, b) => b.insertionTimestamp - a.insertionTimestamp);
  if (orphanedPending.length > 0) {
    const record = orphanedPending[0];
    pendingRecordId = record.id;
    if (!record.reviewStartTimestamp) {
      record.reviewStartTimestamp = Date.now();
    }
    startReviewTimer(record.id);
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    statusBarItem.show();
    if (orphanedPending.length > 1) {
      console.warn(`[AITracker] ${orphanedPending.length} orphaned pending-acceptance records found; resuming the most recent, rest remain stuck.`);
    }
  }

  // Her 60 saniyede bir bekleyen kayıtları yeniden gönder ve süresi dolan
  // gözlem pencerelerini kontrol et
  retryInterval = setInterval(async () => {
    if (supabase.hasPending()) {
      const flushed = await supabase.retryPending();
      if (flushed > 0) {
        console.log(`[AITracker] Retry: ${flushed} record(s) synced.`);
        updateSyncStatus(true);
      }
    }

    const expired = tracker.checkExpiredWindows();
    if (expired.length > 0) {
      for (const record of expired) {
        syncToSupabase(record);
      }
      scheduleSave();
    }
  }, 60_000);

  context.subscriptions.push(
    vscode.commands.registerCommand('aiTracker.acceptCode', handleAccept),
    vscode.commands.registerCommand('aiTracker.viewStats', showStats),
    vscode.commands.registerCommand('aiTracker.exportCSV', exportCSV),
    vscode.commands.registerCommand('aiTracker.setParticipantId', async () => {
      participantId = await askParticipantId(context);
      vscode.window.showInformationMessage(`[AI Tracker] Participant ID set to: ${participantId}`);
    }),
    vscode.commands.registerCommand('aiTracker.pasteIntercept', async () => {
      const editor = vscode.window.activeTextEditor;
      const clipboardText = await vscode.env.clipboard.readText();

      if (!clipboardText || clipboardText.replace(/\s/g, '').length === 0 || !editor || pendingRecordId) {
        await vscode.commands.executeCommand('editor.action.clipboardPasteAction');
        return;
      }

      const startLine = editor.selection.active.line;
      const newlines = (clipboardText.match(/\n/g) ?? []).length;
      const trailingNewline = clipboardText.endsWith('\n') ? 1 : 0;
      const lineCount = newlines - trailingNewline + 1;
      const endLine = startLine + newlines - trailingNewline;

      await vscode.commands.executeCommand('editor.action.clipboardPasteAction');

      const id = generateId();
      const record: InsertionRecord = {
        id,
        insertionTimestamp: Date.now(),
        fileUri: editor.document.uri.toString(),
        fileName: path.basename(editor.document.uri.fsPath),
        originalLineCount: lineCount,
        startLine,
        endLine,
        pendingConfirmation: true,
        pendingAcceptance: false,
        editedBeforeAcceptance: false,
        reviewStartTimestamp: null,
        reviewDurationMs: null,
        condition: null,
        acceptanceTimestamp: null,
        observationWindowEndTimestamp: null,
        selfReportedConfidence: null,
        blockDeleted: false,
        blockDeletionTimestamp: null,
        observationComplete: false,
        lastSynced: null,
        postAcceptance: {
          editSessions: [],
          changedAbsoluteLines: [],
          totalLinesChanged: 0,
          proportionLinesChanged: 0,
          totalActiveModificationTimeMs: 0,
          timeToFirstModificationMs: null
        }
      };

      tracker.add(record);
      pendingRecordId = id;
      promptUser(id, lineCount).catch(err => {
        console.error('[AITracker] promptUser error:', err);
        tracker.remove(id);
        pendingRecordId = null;
      });
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument(event => {
      tracker.handleDocumentChange(
        event,
        record => { scheduleSave(); syncToSupabase(record); },
        record => { scheduleSave(); syncToSupabase(record); }
      );
    })
  );

  console.log(`[AITracker] Activated — participant: ${participantId}`);
}

async function promptUser(id: string, lineCount: number): Promise<void> {
  // Step 1: Was this AI-generated?
  const aiAnswer = await vscode.window.showInformationMessage(
    `Code insertion detected (${lineCount} line${lineCount > 1 ? 's' : ''}). Was this generated by an AI tool (e.g. GitHub Copilot, ChatGPT)?`,
    { modal: true },
    'Yes, AI-generated',
    'No'
  );

  if (aiAnswer !== 'Yes, AI-generated') {
    tracker.reject(id);
    const record = tracker.get(id);
    if (record) {
      syncToSupabase(record);
      scheduleSave();
    }
    pendingRecordId = null;
    return;
  }

  tracker.confirmAI(id);
  const record = tracker.get(id);
  if (!record) return;
  record.pendingAcceptance = true;

  // Step 2: Do you want to modify?
  const modifyAnswer = await vscode.window.showInformationMessage(
    'Do you want to modify this code before accepting?',
    { modal: true },
    'Yes, I\'ll review',
    'No, accept now'
  );

  if (modifyAnswer === 'Yes, I\'ll review') {
    record.reviewStartTimestamp = Date.now();
    record.editedBeforeAcceptance = true;
    startReviewTimer(id);
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  } else {
    record.condition = 'immediate';
    record.reviewDurationMs = 0;
    statusBarItem.backgroundColor = undefined;
    tracker.accept(id);
    record.selfReportedConfidence = await askConfidence();
    vscode.window.showInformationMessage('[AI Tracker] Accepted.');
    syncToSupabase(record);
    pendingRecordId = null;
    statusBarItem.hide();
    scheduleSave();
    return;
  }

  statusBarItem.show();
  scheduleSave();
}

async function askConfidence(): Promise<number | null> {
  const answer = await vscode.window.showInformationMessage(
    'How much do you trust this AI code? (1 = not at all, 5 = completely)',
    { modal: true },
    '1', '2', '3', '4', '5'
  );
  return answer ? parseInt(answer) : null;
}

function startReviewTimer(id: string): void {
  updateStatusBar(id);
  reviewTimerInterval = setInterval(() => updateStatusBar(id), 1000);
}

function updateStatusBar(id: string): void {
  const record = tracker.get(id);
  if (!record || !record.reviewStartTimestamp) return;

  const elapsed = Math.floor((Date.now() - record.reviewStartTimestamp) / 1000);
  const mm = Math.floor(elapsed / 60).toString().padStart(2, '0');
  const ss = (elapsed % 60).toString().padStart(2, '0');

  statusBarItem.text = `$(check) Accept AI Code  |  ${mm}:${ss}`;
  statusBarItem.tooltip = 'Click when done reviewing. Timer shows how long you\'ve been modifying.';
}

function stopReviewTimer(): void {
  if (reviewTimerInterval) {
    clearInterval(reviewTimerInterval);
    reviewTimerInterval = null;
  }
}

async function handleAccept(): Promise<void> {
  if (!pendingRecordId) {
    vscode.window.showInformationMessage('[AI Tracker] No pending AI code block.');
    return;
  }

  const record = tracker.get(pendingRecordId);
  if (record && record.reviewStartTimestamp) {
    record.reviewDurationMs = Date.now() - record.reviewStartTimestamp;
  }

  stopReviewTimer();
  tracker.accept(pendingRecordId);

  const updated = tracker.get(pendingRecordId);
  if (updated) {
    updated.selfReportedConfidence = await askConfidence();
    vscode.window.showInformationMessage('[AI Tracker] Accepted. Tracking modifications for 7 days.');
    syncToSupabase(updated);
  }

  pendingRecordId = null;
  statusBarItem.hide();
  scheduleSave();
}

function showStats(): void {
  StatsPanel.show(tracker.getAll(), participantId);
}

async function exportCSV(): Promise<void> {
  const records = tracker.getAll();
  const csv = dataStore.buildCSV(records);

  const uri = await vscode.window.showSaveDialog({
    defaultUri: vscode.Uri.file(`ai-tracker-${participantId ?? 'data'}.csv`),
    filters: { CSV: ['csv'] }
  });

  if (!uri) return;

  fs.writeFileSync(uri.fsPath, csv, 'utf8');
  vscode.window.showInformationMessage(`[AI Tracker] Exported to ${uri.fsPath}`);
}

function syncToSupabase(record: InsertionRecord): void {
  if (!participantId) return;
  backupStore.append(record, participantId);
  supabase.sync(record, participantId)
    .then(ok => {
      if (ok) {
        record.lastSynced = Date.now();
        scheduleSave();
      }
      updateSyncStatus(ok);
    })
    .catch(err => {
      console.error('[AITracker] Supabase sync failed:', err);
      updateSyncStatus(false);
    });
}

function updateSyncStatus(lastOk: boolean): void {
  const pending = supabase.getPendingCount();
  if (pending > 0) {
    syncStatusItem.text = `$(sync-ignored) Sync: ${pending} pending`;
    syncStatusItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  } else if (lastOk) {
    syncStatusItem.text = '$(check) Sync: OK';
    syncStatusItem.backgroundColor = undefined;
  } else {
    syncStatusItem.text = '$(warning) Sync: error';
    syncStatusItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
  }
}

function scheduleSave(): void {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => dataStore.save(tracker.getAll()), 2000);
}

export function deactivate(): void {
  stopReviewTimer();
  if (retryInterval) {
    clearInterval(retryInterval);
    retryInterval = null;
  }
  if (saveTimer) {
    clearTimeout(saveTimer);
    dataStore.save(tracker.getAll());
  }
}

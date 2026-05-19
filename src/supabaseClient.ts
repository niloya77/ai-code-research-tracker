import * as https from 'https';
import * as vscode from 'vscode';
import { InsertionRecord } from './types';

interface SupabaseRow {
  record_id: string;
  participant_id: string;
  insertion_timestamp: number;
  file_name: string;
  original_line_count: number;
  condition: string | null;
  acceptance_timestamp: number | null;
  time_to_accept_ms: number | null;
  edited_before_acceptance: boolean;
  total_lines_changed: number;
  proportion_lines_changed: number;
  change_frequency: number;
  total_active_modification_time_ms: number;
  time_to_first_modification_ms: number | null;
  observation_complete: boolean;
  review_duration_ms: number | null;
  last_synced: number;
}

const DEFAULT_URL = 'https://wvyrgdbjmxfnmduzhnha.supabase.co';
const DEFAULT_KEY = 'sb_publishable_ZeDW_bl7vuno6k4oFBp71Q_QGowtcgI';

export class SupabaseClient {
  private supabaseUrl: string;
  private supabaseKey: string;

  constructor() {
    const cfg = vscode.workspace.getConfiguration('aiTracker');
    this.supabaseUrl = (cfg.get<string>('supabaseUrl', '') || DEFAULT_URL).replace(/\/$/, '');
    this.supabaseKey = cfg.get<string>('supabaseKey', '') || DEFAULT_KEY;
  }

  isConfigured(): boolean {
    return this.supabaseUrl.length > 0 && this.supabaseKey.length > 0;
  }

  async sync(record: InsertionRecord, participantId: string): Promise<void> {
    if (!this.isConfigured()) return;

    const now = Date.now();
    const observationDone =
      record.observationWindowEndTimestamp !== null &&
      now > record.observationWindowEndTimestamp;

    const row: SupabaseRow = {
      record_id: record.id,
      participant_id: participantId,
      insertion_timestamp: record.insertionTimestamp,
      file_name: record.fileName,
      original_line_count: record.originalLineCount,
      condition: record.condition,
      acceptance_timestamp: record.acceptanceTimestamp,
      time_to_accept_ms:
        record.acceptanceTimestamp !== null
          ? record.acceptanceTimestamp - record.insertionTimestamp
          : null,
      edited_before_acceptance: record.editedBeforeAcceptance,
      total_lines_changed: record.postAcceptance.totalLinesChanged,
      proportion_lines_changed: record.postAcceptance.proportionLinesChanged,
      change_frequency: record.postAcceptance.changeFrequency,
      total_active_modification_time_ms:
        record.postAcceptance.totalActiveModificationTimeMs,
      time_to_first_modification_ms:
        record.postAcceptance.timeToFirstModificationMs,
      observation_complete: observationDone,
      review_duration_ms: record.reviewDurationMs ?? null,
      last_synced: now
    };

    await this.upsert(row);
  }

  private upsert(row: SupabaseRow): Promise<void> {
    return new Promise(resolve => {
      const body = JSON.stringify([row]);
      const urlObj = new URL(`${this.supabaseUrl}/rest/v1/insertion_records`);

      const options: https.RequestOptions = {
        hostname: urlObj.hostname,
        path: urlObj.pathname,
        method: 'POST',
        headers: {
          apikey: this.supabaseKey,
          Authorization: `Bearer ${this.supabaseKey}`,
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
          Prefer: 'resolution=merge-duplicates'
        }
      };

      const req = https.request(options, res => {
        res.resume();
        res.on('end', resolve);
      });

      req.on('error', err => {
        console.error('[AITracker] Supabase sync error:', err.message);
        resolve();
      });

      req.write(body);
      req.end();
    });
  }
}

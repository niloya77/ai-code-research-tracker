import * as vscode from 'vscode';
import { InsertionRecord } from './types';

export class StatsPanel {
  static currentPanel: StatsPanel | undefined;

  private readonly _panel: vscode.WebviewPanel;
  private _disposables: vscode.Disposable[] = [];

  static show(records: InsertionRecord[], participantId: string | null): void {
    if (StatsPanel.currentPanel) {
      StatsPanel.currentPanel._panel.reveal(vscode.ViewColumn.One);
      StatsPanel.currentPanel._update(records, participantId);
      return;
    }
    const panel = vscode.window.createWebviewPanel(
      'aiTrackerStats',
      'AI Tracker — Statistics',
      vscode.ViewColumn.One,
      { enableScripts: false }
    );
    StatsPanel.currentPanel = new StatsPanel(panel, records, participantId);
  }

  private constructor(
    panel: vscode.WebviewPanel,
    records: InsertionRecord[],
    participantId: string | null
  ) {
    this._panel = panel;
    this._update(records, participantId);
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
  }

  private _update(records: InsertionRecord[], participantId: string | null): void {
    this._panel.webview.html = buildHtml(records, participantId);
  }

  dispose(): void {
    StatsPanel.currentPanel = undefined;
    this._panel.dispose();
    this._disposables.forEach(d => d.dispose());
  }
}

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function avg(arr: InsertionRecord[], fn: (r: InsertionRecord) => number): string {
  if (arr.length === 0) return '—';
  return (arr.reduce((s, r) => s + fn(r), 0) / arr.length).toFixed(2);
}

function buildHtml(records: InsertionRecord[], participantId: string | null): string {
  const filtered = records.filter(r => r.condition !== null);
  const reviewed = filtered.filter(r => r.condition === 'reviewed');
  const immediate = filtered.filter(r => r.condition === 'immediate');
  const rejected = filtered.filter(r => r.condition === 'rejected');

  const tableRows = [...filtered].reverse().map(r => {
    const ts = new Date(r.insertionTimestamp).toLocaleString();
    const dur = r.reviewDurationMs != null ? (r.reviewDurationMs / 1000).toFixed(1) + 's' : '—';
    const conf = r.selfReportedConfidence != null ? r.selfReportedConfidence + ' / 5' : '—';
    const pct = (r.postAcceptance.proportionLinesChanged * 100).toFixed(1) + '%';
    const cond = r.condition ?? '';
    return `<tr>
      <td>${esc(ts)}</td>
      <td title="${esc(r.fileUri)}">${esc(r.fileName)}</td>
      <td class="num">${r.originalLineCount}</td>
      <td><span class="badge ${esc(cond)}">${esc(cond)}</span></td>
      <td class="num">${dur}</td>
      <td class="num">${conf}</td>
      <td class="num">${pct}</td>
      <td class="num">${r.postAcceptance.totalLinesChanged}</td>
    </tr>`;
  }).join('');

  const avgReviewDur   = avg(reviewed,  r => (r.reviewDurationMs ?? 0) / 1000);
  const avgPctReviewed = avg(reviewed,  r => r.postAcceptance.proportionLinesChanged * 100);
  const avgPctImmediat = avg(immediate, r => r.postAcceptance.proportionLinesChanged * 100);
  const avgEditReview  = avg(reviewed,  r => r.postAcceptance.totalActiveModificationTimeMs / 1000);
  const avgEditImmed   = avg(immediate, r => r.postAcceptance.totalActiveModificationTimeMs / 1000);
  const confAll        = filtered.filter(r => r.selfReportedConfidence != null);
  const avgConf        = avg(confAll,   r => r.selfReportedConfidence ?? 0);

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Tracker Statistics</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: var(--vscode-font-family, system-ui, sans-serif);
    font-size: var(--vscode-font-size, 13px);
    color: var(--vscode-foreground);
    background: var(--vscode-editor-background);
    padding: 28px 32px 48px;
    line-height: 1.5;
  }

  /* ── Header ── */
  .header { margin-bottom: 28px; }
  .header h1 {
    font-size: 1.35em;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--vscode-foreground);
  }
  .header .sub {
    margin-top: 3px;
    font-size: 0.85em;
    color: var(--vscode-descriptionForeground);
  }
  .header .sub strong { color: var(--vscode-foreground); }

  /* ── Section title ── */
  h2 {
    font-size: 0.7em;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--vscode-descriptionForeground);
    margin-bottom: 12px;
  }

  /* ── Cards ── */
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 12px;
    margin-bottom: 32px;
  }
  .card {
    border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25));
    border-radius: 8px;
    padding: 14px 18px 12px;
    background: var(--vscode-sideBar-background, rgba(0,0,0,.15));
  }
  .card .val {
    font-size: 2.2em;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 5px;
  }
  .card .lbl {
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--vscode-descriptionForeground);
  }
  .card.total   .val { color: var(--vscode-foreground); }
  .card.reviewed  .val { color: #4ec9b0; }
  .card.immediate .val { color: #569cd6; }
  .card.rejected  .val { color: #f48771; }

  /* ── Averages grid ── */
  .avg-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 10px;
    margin-bottom: 32px;
  }
  .avg-box {
    border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25));
    border-radius: 6px;
    padding: 10px 14px;
    background: var(--vscode-sideBar-background, rgba(0,0,0,.15));
  }
  .avg-box .alabel {
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--vscode-descriptionForeground);
    margin-bottom: 6px;
  }
  .avg-row { display: flex; gap: 14px; flex-wrap: wrap; }
  .avg-row .aval {
    font-size: 1em;
    font-weight: 600;
    color: var(--vscode-foreground);
  }
  .avg-row .aval .atag {
    font-size: 0.72em;
    font-weight: 400;
    color: var(--vscode-descriptionForeground);
    margin-left: 2px;
  }

  /* ── Table ── */
  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25));
    border-radius: 8px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.87em;
  }
  thead th {
    padding: 9px 14px;
    text-align: left;
    font-size: 0.74em;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--vscode-descriptionForeground);
    border-bottom: 1px solid var(--vscode-panel-border, rgba(128,128,128,.25));
    background: var(--vscode-sideBar-background, rgba(0,0,0,.1));
    white-space: nowrap;
  }
  tbody tr { border-bottom: 1px solid var(--vscode-panel-border, rgba(128,128,128,.12)); }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: var(--vscode-list-hoverBackground, rgba(128,128,128,.08)); }
  tbody td { padding: 8px 14px; vertical-align: middle; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }

  .badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 4px;
    font-size: 0.8em;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .badge.reviewed  { background: rgba(78,201,176,.18);  color: #4ec9b0; }
  .badge.immediate { background: rgba(86,156,214,.18);  color: #569cd6; }
  .badge.rejected  { background: rgba(244,135,113,.18); color: #f48771; }

  .empty {
    padding: 48px;
    text-align: center;
    color: var(--vscode-descriptionForeground);
    font-style: italic;
  }

  /* ── Divider ── */
  .section { margin-bottom: 28px; }
</style>
</head>
<body>

<div class="header">
  <h1>AI Code Research Tracker</h1>
  <p class="sub">Participant: <strong>${esc(participantId ?? 'unknown')}</strong></p>
</div>

<div class="section">
  <h2>Summary</h2>
  <div class="cards">
    <div class="card total">
      <div class="val">${filtered.length}</div>
      <div class="lbl">Total</div>
    </div>
    <div class="card reviewed">
      <div class="val">${reviewed.length}</div>
      <div class="lbl">Reviewed</div>
    </div>
    <div class="card immediate">
      <div class="val">${immediate.length}</div>
      <div class="lbl">Immediate</div>
    </div>
    <div class="card rejected">
      <div class="val">${rejected.length}</div>
      <div class="lbl">Rejected</div>
    </div>
  </div>
</div>

<div class="section">
  <h2>Averages</h2>
  <div class="avg-grid">
    <div class="avg-box">
      <div class="alabel">Review Duration</div>
      <div class="avg-row">
        <span class="aval">${avgReviewDur}s <span class="atag">reviewed</span></span>
      </div>
    </div>
    <div class="avg-box">
      <div class="alabel">Lines Changed</div>
      <div class="avg-row">
        <span class="aval">${avgPctReviewed}% <span class="atag">reviewed</span></span>
        <span class="aval">${avgPctImmediat}% <span class="atag">immediate</span></span>
      </div>
    </div>
    <div class="avg-box">
      <div class="alabel">Active Edit Time</div>
      <div class="avg-row">
        <span class="aval">${avgEditReview}s <span class="atag">reviewed</span></span>
        <span class="aval">${avgEditImmed}s <span class="atag">immediate</span></span>
      </div>
    </div>
    <div class="avg-box">
      <div class="alabel">Confidence</div>
      <div class="avg-row">
        <span class="aval">${avgConf} <span class="atag">/ 5</span></span>
      </div>
    </div>
  </div>
</div>

<div class="section">
  <h2>All Insertions</h2>
  ${filtered.length === 0
    ? '<div class="empty">No records yet. Start coding with an AI tool to see data here.</div>'
    : `<div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>File</th>
          <th>Lines</th>
          <th>Condition</th>
          <th>Review Time</th>
          <th>Confidence</th>
          <th>% Changed</th>
          <th>Lines Changed</th>
        </tr>
      </thead>
      <tbody>
        ${tableRows}
      </tbody>
    </table>
  </div>`}
</div>

</body>
</html>`;
}

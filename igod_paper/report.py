"""Consultable simulation results; no account data and no profitability claims."""
from datetime import datetime, timezone
import json
from pathlib import Path

from .journal import atomic_json
from .market import VENUE


def utc(stamp):
    return datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat() if stamp is not None else None


def build(journal, status='HEALTHY', error=None, now=None):
    s = journal.records[-1]['state_after']
    trades = [r['payload']['closed_trade'] for r in journal.records if r['type'] == 'CLOSED_BAR_PROCESSED' and r['payload']['closed_trade']]
    positive = sum(max(0., t['net_pnl']) for t in trades)
    negative = -sum(min(0., t['net_pnl']) for t in trades)
    decisions = [r for r in journal.records if r['type'] == 'SIGNAL_OBSERVED']
    latest = decisions[-1] if decisions else None
    return dict(mode='SHADOW ONLY / PAPER SIMULATION', trade_authority='NONE',
                configuration_hash=journal.records[0]['payload']['configuration_hash'],
                venue=VENUE, symbol='BTCUSDT', status=status, error_code=error,
                evidence='INSUFFICIENT — NOT A VALIDATED EDGE',
                started_at=utc(s['activated_at']), updated_at=utc(now),
                last_closed_bar=utc(s['last_bar']), journal_records=len(journal.records),
                latest_confirmed_decision=latest['payload']['context'] if latest else None,
                latest_decision_observed_at=utc(latest['observed_at']) if latest else None,
                journal_tip=journal.records[-1]['record_hash'], initial_equity=s['initial_equity'],
                realized_equity=s['equity'], equity_after_estimated_exit_cost=s['equity_marked'],
                realized_net=sum(t['net_pnl'] for t in trades), closed_trades=s['trades'],
                wins=s['wins'], losses=s['losses'], breakeven=s['breakeven'],
                win_rate=s['wins'] / s['trades'] if s['trades'] else None,
                profit_factor=positive / negative if negative else None,
                max_marked_drawdown_pct=100 * s['max_drawdown'],
                gross_pnl=s['gross'], fees=s['fees'], funding_paid_net=s['funding'],
                exposure_bars=s['exposure_bars'], observed_bars=s['bars'],
                open_paper_position=s['position'], pending_paper_plan=s['pending'],
                trades=trades,
                limitations=[
                    'Actual public prices; fills, fees and slippage are simulated assumptions, not Bitunix fills.',
                    'Signals reuse Manual Copilot rules on USD-M, not its production Spot feed; LOW27 is not the LOW29 host.',
                    'ATR stops/1.5R targets inherit unvalidated V0 defaults; structural invalidation and 24h time limit are declared adapters.',
                    'No live positions, real funds, execution clients, Telegram, margin or liquidation simulation.',
                    'MFE is a lower bound on exit candles; MAE uses candle extremes and can overestimate pre-exit adversity.',
                    'Drawdown is measured at processed five-minute closes, not a guaranteed intrabar/account risk cap.',
                    'Restarts manage previously committed plans; missed historical signals are never created as forward events.',
                ])


def markdown(report):
    r = report
    lines = ['# I-GOD — resultados PAPER forward', '',
             '**SHADOW ONLY. TRADE AUTHORITY: NONE.**', '',
             'Datos públicos reales; operaciones y capital completamente simulados.', '',
             '| Métrica | Valor |', '|---|---|']
    for key in ('status', 'venue', 'started_at', 'updated_at', 'initial_equity', 'realized_equity',
                'equity_after_estimated_exit_cost', 'closed_trades', 'wins', 'losses',
                'gross_pnl', 'fees', 'funding_paid_net', 'realized_net', 'max_marked_drawdown_pct', 'evidence'):
        lines.append(f'| {key} | {r[key]} |')
    lines += ['', '## Operaciones cerradas', '',
              '| Señal disponible UTC | Entrada UTC | Lado | Entrada | Salida | Motivo | Neto | R neto |',
              '|---|---|---|---:|---:|---|---:|---:|']
    for t in r['trades']:
        lines.append(f"| {utc(t['observed_at'])} | {utc(t['entry_ts'])} | {t['side']} | {t['entry']:.2f} | {t['exit']:.2f} | {t['exit_reason']} | {t['net_pnl']:.6f} | {t['net_r']:.4f} |")
    if not r['trades']:
        lines += ['', 'Sin operaciones cerradas observadas todavía. No se han fabricado señales.']
    decision = r.get('latest_confirmed_decision')
    if decision:
        lines += ['', '## Última decisión realmente observada', '',
                  '| Campo | Valor |', '|---|---|',
                  '| observed_at | ' + str(r['latest_decision_observed_at']) + ' |']
        for key in ('bias', 'why', 'entry_quality', 'entry_reason', 'trend1', 'trend4', 'momentum', 'flow', 'structure', 'pattern'):
            lines.append('| ' + key + ' | ' + str(decision.get(key)) + ' |')
        levels = decision.get('market_levels') or {}
        for key in ('support', 'resistance'):
            lines.append('| confirmed_' + key + ' | ' + str(levels.get(key)) + ' |')
    lines += ['', '## Límites', ''] + ['- ' + item for item in r['limitations']]
    return '\n'.join(lines) + '\n'


def publish(directory, report):
    directory = Path(directory)
    atomic_json(directory / 'report.json', report)
    temporary = directory / 'report.md.tmp'
    temporary.write_text(markdown(report), encoding='utf-8')
    temporary.replace(directory / 'report.md')

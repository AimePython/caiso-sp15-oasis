"""Standard-library-only research tools, also installed into the existing local MCP.

This is an API-level separation, not an operating-system access-control boundary.
The legacy archive/query_sql tools remain available for retrospective analysis.
"""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import date,datetime,time,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_ROOT = '/Users/jins/Documents/ChatGPT/比赛/research/experiments/sp15_dam_20260701_20261030_v1'
NOTICE = 'Historical extraction backtest. Source publication vintages unavailable; midnight availability is an assumption. No live trading.'


def root():
    return Path(os.environ.get('SP15_RESEARCH_ROOT',DEFAULT_ROOT))


def settings():
    return json.loads((root()/'config.json').read_text())


def _page(path,table,where,params,limit=168,offset=0):
    if not isinstance(limit,int) or not 1<=limit<=5000 or not isinstance(offset,int) or offset<0:
        raise ValueError('Require limit 1..5000 and offset >= 0.')
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as conn:
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        total=conn.execute(f'SELECT count(*) FROM {table} WHERE {where}',params).fetchone()[0]
        rows=[dict(r) for r in conn.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY timestamp LIMIT ? OFFSET ?',[*params,limit,offset])]
    return dict(rows=rows,total=total,offset=offset,next_offset=offset+len(rows) if offset+len(rows)<total else None,notice=NOTICE)


def research_catalog():
    cfg=settings()
    return dict(experiment=cfg,source_catalog=json.loads((root()/'audit/source_catalog.json').read_text()),
        partitions=[
            dict(name='raw_archive',purpose='Daily ingestion only; existing source MCP; never write predictions here',path=cfg['source_db']),
            dict(name='training',purpose='Only operating dates before 2026-07-01; labels allowed for fit',path=str(root()/'training/data.sqlite')),
            dict(name='observations',purpose='Past-day values released through prediction_inputs gate; never refit parameters',path=str(root()/'observations/data.sqlite')),
            dict(name='evaluation',purpose='Holdout truth for separate scorer only; not exposed by training tools',path=str(root()/'evaluation/data.sqlite')),
            dict(name='predictions',purpose='Model output only; no actual price column',path=str(root()/'predictions/results.sqlite'))],
        forbidden_contemporaneous_features=['target LMP and components','other-node same-day DAM prices','same-day AS cleared prices',
            'same-day DAM tie usage/ATC','same-day constraint shadow prices'],
        legacy_training_panel='Retrospective same-hour join; NOT a leakage-safe supervised forecasting dataset.',notice=NOTICE)


def research_training(start='2023-08-01',end='2026-06-30',limit=168,offset=0):
    cfg=settings();a=date.fromisoformat(start);b=date.fromisoformat(end)
    if b<a or a<date.fromisoformat(cfg['history_start']) or b>=date.fromisoformat(cfg['train_end_exclusive']):
        raise ValueError('Training dates must remain inside frozen pre-2026-07-01 history; end is inclusive.')
    return _page(root()/'training/data.sqlite','training_prices','market_date>=? AND market_date<=?',[start,end],limit,offset)


def research_prediction_inputs(day,limit=168,offset=0):
    cfg=settings();d=date.fromisoformat(day)
    if not date.fromisoformat(cfg['test_start'])<=d<=date.fromisoformat(cfg['test_end_inclusive']):
        raise ValueError('Forecast day must be within the frozen historical backtest window.')
    tz=ZoneInfo(cfg['timezone'])
    origin=datetime.combine(d-timedelta(days=1),time(9,55),tzinfo=tz)
    start=(datetime.combine(d,time(),tzinfo=tz).astimezone(timezone.utc)-timedelta(hours=168)).strftime('%Y-%m-%dT%H:%M:%SZ')
    cutoff=origin.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    result=_page(root()/'observations/data.sqlite','observations',
        'market_date<? AND assumed_available_at<=? AND timestamp>=?',[day,cutoff,start],limit,offset)
    result.update(forecast_origin=origin.isoformat(),target_day=day,parameter_refit_allowed=False)
    return result


def research_predictions(model,start='2026-07-01',end='2026-10-30',limit=168,offset=0):
    date.fromisoformat(start);date.fromisoformat(end)
    if end<start:raise ValueError('Invalid date interval')
    return _page(root()/'predictions/results.sqlite','predictions','model=? AND market_date>=? AND market_date<=?',
                 [model,start,end],limit,offset)


def research_metrics():
    return json.loads((root()/'evaluation/summary.json').read_text())


def register(mcp):
    tools=[(research_catalog,'List source classifications and physically separated frozen research partitions.'),
        (research_training,'Read training labels ONLY before July 2026. Inclusive California operating dates. Cannot return holdout truth.'),
        (research_prediction_inputs,'Read a past-only 168-hour input window for a backtest day at D-1 09:55 PT. Cannot refit on these observations.'),
        (research_predictions,'Read model forecasts from the predictions-only database, never training data or actual prices.'),
        (research_metrics,'Read aggregate historical backtest metrics. No live trading performance.')]
    for fn,description in tools:
        mcp.tool(name=fn.__name__,description=description,structured_output=False)(fn)


if __name__=='__main__':
    from mcp.server.mcpserver import MCPServer
    mcp=MCPServer('caiso-sp15-research',instructions=NOTICE)
    register(mcp)
    mcp.run()

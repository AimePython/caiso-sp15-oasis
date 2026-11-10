"""Meaningful time-boundary, feature-leakage, DST and artifact-separation checks."""
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sp15_research import data,mcp_api
from sp15_research.models import regression_features,vmd_windows


def test_full_frozen_grid_and_split():
    root=data.experiment_root();data.verify_frozen()
    train=pd.read_csv(root/'training/prices.csv');truth=pd.read_csv(root/'evaluation/prices.csv')
    assert len(train)==25560 and len(truth)==2928
    assert train.market_date.max()=='2026-06-30'
    assert truth.market_date.min()=='2026-07-01' and truth.market_date.max()=='2026-10-30'
    assert set(train.timestamp).isdisjoint(truth.timestamp)
    assert (train.price<0).any() and (truth.price<0).any()


def test_future_poison_cannot_change_past_inputs(tmp_path):
    root=tmp_path
    (root/'observations').mkdir()
    with data.read_only(data.experiment_root()/'observations/data.sqlite') as src:
        with sqlite3.connect(root/'observations/data.sqlite') as dst:src.backup(dst)
    before=data.known_history('2026-08-10',root)
    with sqlite3.connect(root/'observations/data.sqlite') as dst:
        dst.execute("UPDATE observations SET price=99999999 WHERE market_date>='2026-08-10'")
    pd.testing.assert_series_equal(before,data.known_history('2026-08-10',root))
    assert before.index[-1].tz_convert(data.TZ).strftime('%Y-%m-%d')=='2026-08-09'


def test_unavailable_past_observation_is_not_returned(tmp_path):
    (tmp_path/'observations').mkdir()
    with data.read_only(data.experiment_root()/'observations/data.sqlite') as src:
        with sqlite3.connect(tmp_path/'observations/data.sqlite') as dst:src.backup(dst)
    with sqlite3.connect(tmp_path/'observations/data.sqlite') as dst:
        dst.execute("UPDATE observations SET assumed_available_at='2026-08-11T00:00:00Z' WHERE market_date='2026-08-09'")
    got=data.known_history('2026-08-10',tmp_path)
    assert got.index[-1].tz_convert(data.TZ).strftime('%Y-%m-%d')=='2026-08-08'


def test_training_rejects_holdout_and_sql_parameters():
    with pytest.raises(ValueError):mcp_api.research_training(end='2026-07-01')
    with pytest.raises(ValueError):mcp_api.research_training(start="2023-08-01' OR 1=1 --")
    with pytest.raises(ValueError):mcp_api.research_training(limit=0)
    with pytest.raises(ValueError):mcp_api.research_prediction_inputs('2026-11-01')


def test_no_target_in_mcp_window():
    out=mcp_api.research_prediction_inputs('2026-07-01')
    assert len(out['rows'])==168
    assert all(r['market_date']<'2026-07-01' for r in out['rows'])
    assert out['forecast_origin']=='2026-06-30T09:55:00-07:00'
    assert out['parameter_refit_allowed'] is False


def test_dst_and_training_targets():
    assert len(data.target_index('2026-03-08'))==23
    assert len(data.target_index('2025-11-02'))==25
    train=data.load_training();x,y,dates=data.daily_samples(train)
    assert x.shape[1]==168 and y.shape[1]==24
    assert max(dates)=='2026-06-30'
    assert '2026-03-08' not in dates
    assert '2025-11-02' not in dates


def test_vmd_reconstructs_only_input_and_deterministic():
    x=data.load_training().iloc[-168:].to_numpy()[None,:]
    a=vmd_windows(x);b=vmd_windows(x)
    np.testing.assert_allclose(a,b)
    np.testing.assert_allclose(a.sum(axis=2),x,rtol=1e-5,atol=1e-4)
    assert a.shape==(1,168,5)


def test_prediction_db_has_no_truth_or_training_tables():
    path=data.experiment_root()/'predictions/results.sqlite'
    if not path.exists():pytest.skip('Prediction runner not yet started')
    with data.read_only(path) as conn:
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns={r[1] for r in conn.execute('PRAGMA table_info(predictions)')}
    assert tables=={'predictions'}
    assert 'prediction' in columns and not {'price','actual','truth'} & columns


def test_direct_regression_features_do_not_accept_target_values():
    x=np.arange(168,dtype=float)[None,:]
    z=regression_features(x,['2026-07-01'])
    np.testing.assert_array_equal(z[:,0],x[0,-24:])
    np.testing.assert_array_equal(z[:,2],x[0,:24])
    assert z.shape==(24,14)


def test_frozen_state_updates_equal_filter_without_refit():
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from sp15_research.models import StateSpace
    idx=pd.date_range('2026-06-20',periods=264,freq='h',tz=data.TZ).tz_convert('UTC')
    values=np.sin(np.arange(264)/6)+np.arange(264)*0.01
    history=pd.Series(values,index=idx)
    params=np.array([0.8,0.5])
    obj=StateSpace.__new__(StateSpace)
    obj.exogenous=False;obj.mean=0.;obj.std=1.;obj.last=idx[239]
    obj.result=SARIMAX(values[:240],order=(1,0,0)).filter(params,low_memory=True)
    before=obj.result.params.copy()
    forecast=obj.predict(history,'2026-07-01')
    expected=SARIMAX(values,order=(1,0,0)).filter(params).forecast(24)
    np.testing.assert_allclose(forecast,expected,rtol=1e-10,atol=1e-10)
    np.testing.assert_array_equal(before,obj.result.params)

"""原 sp15_oasis MCP 的天气桥接：共用研究档案库，不修改原电价数据库。"""
from pathlib import Path
import os
import subprocess
import sys

PROJECT=Path('/Users/jins/Documents/ChatGPT/比赛')
SERVICE=PROJECT/'mcp_service'
DB=SERVICE/'runtime/caiso.sqlite'


def _backend():
    service=Path(os.environ.get('SP15_WEATHER_SERVICE_ROOT',str(SERVICE)))
    if str(service) not in sys.path:sys.path.insert(0,str(service))
    from caiso_mcp.store import Store
    from caiso_mcp import weather
    return Store(os.environ.get('SP15_WEATHER_DB',str(DB))),weather


def register(mcp):
    @mcp.tool(name='list_weather_datasets',structured_output=False)
    def list_weather_datasets()->dict:
        """气象预报目录：Open-Meteo 的变量、地点、覆盖、单位；不属于实测数据。"""
        store,weather=_backend();return weather.weather_catalog(store)

    @mcp.tool(name='query_weather_forecast',structured_output=False)
    def query_weather_forecast(start:str,end:str,location:str|None=None,variable:str|None=None,
            run:str|None=None,limit:int=168,offset:int=0,as_of:str|None=None,snapshot:str|None=None)->dict:
        """读取气象预报。start 含、end 不含，日期按加州零点；时间戳需带时区。
        location 例如 los_angeles/san_diego/riverside/palm_springs/tehachapi/fresno/redding。
        variable: temperature_2m, wind_speed_10m, shortwave_radiation, cloud_cover, precipitation。
        run 可选，指定 UTC 起报批次；不传时查询实时采集快照。as_of 按真实采集时刻过滤。
        历史起报时间不是发布时间；不自动将历史回补纳入当时已知特征。辐照/降水已对齐小时起点。
        """
        if limit>500:raise ValueError('Weather MCP maximum limit is 500')
        store,weather=_backend()
        return weather.query_weather(store,start,end,location,variable,run,limit,offset,as_of,snapshot)


def sync_weather_once():
    """既有 01:15 watch 入口先采天气；超时/失败可见，但不阻断原 OASIS 补采。"""
    env=dict(os.environ,PYTHONPATH=str(SERVICE))
    args=[str(PROJECT/'.venv-mcp/bin/python'),'-m','caiso_mcp','--db',str(DB),
          'weather-fetch','--locations',str(SERVICE/'config/weather_locations.json'),
          '--raw-dir',str(SERVICE/'runtime/raw/weather')]
    try:
        result=subprocess.run(args,env=env,cwd=PROJECT,capture_output=True,text=True,timeout=180)
        if result.returncode:
            print('[weather] failed: '+result.stderr[-1500:],file=sys.stderr)
        else:print('[weather] '+result.stdout.strip(),file=sys.stderr)
        return result.returncode
    except (OSError,subprocess.TimeoutExpired) as exc:
        print('[weather] failed: '+str(exc),file=sys.stderr);return 1

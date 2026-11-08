"""Offline tests. These do not call CAISO."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sp15_oasis.calendar import expected_hours, floor_chunk, iter_chunks, trading_bounds
from sp15_oasis.catalog import HUB, classify_nomogram, node_ids, tie_ids
from sp15_oasis.db import connect, upsert
from sp15_oasis.freshness import AS_REQUIREMENTS, AS_TYPES, LMP_TYPES, TIE_DIRECTIONS, day_gaps
from sp15_oasis.parse import normalize_lmp, normalize_usage
from sp15_oasis.query import query_sql, training_panel
from sp15_oasis.watch import run_watch


class CalendarTests(unittest.TestCase):
    def test_chunk_grid_starts_on_the_retention_floor(self):
        self.assertEqual(floor_chunk(date(2023, 8, 1)), date(2023, 8, 1))
        self.assertEqual(floor_chunk(date(2023, 8, 31)), date(2023, 8, 1))
        self.assertEqual(floor_chunk(date(2023, 9, 1)), date(2023, 9, 1))
        self.assertEqual(
            list(iter_chunks(date(2023, 8, 15), date(2023, 8, 15))),
            [(date(2023, 8, 1), date(2023, 9, 1))],
        )

    def test_trading_bounds_follow_pacific_daylight_time(self):
        # 2026-03-08 is the spring-forward; midnight is still PST, the next midnight is PDT.
        self.assertEqual(
            trading_bounds(date(2026, 3, 8), date(2026, 3, 9)),
            ("20260308T08:00-0000", "20260309T07:00-0000"),
        )
        # 2026-11-01 is the fall-back; midnight is still PDT, the next midnight is PST.
        self.assertEqual(
            trading_bounds(date(2026, 11, 1), date(2026, 11, 2)),
            ("20261101T07:00-0000", "20261102T08:00-0000"),
        )

    def test_expected_hours_follow_pacific_daylight_time(self):
        self.assertEqual(expected_hours(date(2026, 11, 7)), 24)
        self.assertEqual(expected_hours(date(2026, 3, 8)), 23)
        self.assertEqual(expected_hours(date(2026, 11, 1)), 25)


class ClassifyTests(unittest.TestCase):
    def test_sample_day_constraints(self):
        expected = {
            "22020- 23497 AVOCDO-FALBRK_69_BR_1_1": "sp15",
            "22208_EL CAJON_69.0_22408_LOSCOCHS_69.0_BR_1 _1": "sp15",
            "22412_LOSCOCHS_138_22734_SANTEE  _138_BR_1 _1": "sp15",
            "22480_MIRAMAR _69.0_22756_SCRIPPS _69.0_BR_1 _1": "sp15",
            "24155_VINCENT _230_24128_S.CLARA _230_BR_1 _1": "sp15",
            "24957_COLRIVER_230_24900_COLRIVER_500_XF_2 _P": "sp15",
            "30055_GATES1  _500_30060_MIDWAY  _500_BR_1 _1": "path15",
            "30060_MIDWAY  _500_24156_VINCENT _500_BR_1 _3": "sp15",
            "30790_PANOCHE _230_30900_GATES   _230_BR_1 _1": "path15",
            "30900_GATES   _230_30935_ARCO    _230_BR_1 _1": "path15",
            "31227_HGHLNDJ2_115_31950_CORTINA _115_BR_1 _1": "other",
            "32225_BRNSWKT1_115_32222_DTCH2TAP_115_BR_1 _1": "other",
            "34116_LE GRAND_115_34115_ADRA TAP_115_BR_1 _1": "other",
            "34540_HENRITTA_70.0_30881_HENRIETA_230_XF_4": "path15",
            "34548_KETTLEMN_70.0_34552_GATES   _70.0_BR_1 _1": "path15",
            "36850_KIFER   _115_35615_FMC     _115_BR_1 _1": "other",
            "36851_NORTHERN_115_36852_SCOTT   _115_BR_2 _1": "other",
            "38615_DS AMIGO_230_30790_PANOCHE _230_BR_1 _1": "path15",
            "7690-CONTRL-INYOKN_EXP_NG": "sp15",
            "7760_DEV_RDB_ALIS": "sp15",
            "7820_TL23040_IV_SPS_NG": "sp15",
            "7820_TL649A_OVERLOAD_NG": "sp15",
            "8610_SylmarBNK_N-S_Import_NG": "sp15",
        }
        for name, tag in expected.items():
            self.assertEqual(classify_nomogram(name), tag, name)


class ParseTests(unittest.TestCase):
    def test_lmp_keeps_the_component_name(self):
        rows = normalize_lmp(
            [
                {
                    "INTERVALSTARTTIME_GMT": "2026-11-07T08:00:00-00:00",
                    "INTERVALENDTIME_GMT": "2026-11-07T09:00:00-00:00",
                    "OPR_DT": "2026-11-07",
                    "OPR_HR": "1",
                    "NODE": "TH_SP15_GEN-APND",
                    "LMP_TYPE": "LMP",
                    "XML_DATA_ITEM": "LMP_PRC",
                    "MW": "57.85855",
                }
            ]
        )
        self.assertEqual(rows[0]["value"], 57.85855)
        self.assertEqual(rows[0]["lmp_type"], "LMP")

    def test_usage_pivots_one_hour(self):
        base = {
            "INTERVALSTARTTIME_GMT": "2026-11-07T08:00:00-00:00",
            "INTERVALENDTIME_GMT": "2026-11-07T09:00:00-00:00",
            "OPR_DT": "2026-11-07",
            "OPR_HR": "1",
            "TI_ID": "PALOVRDE_ITC",
            "TI_DIRECTION": "I",
        }
        rows = normalize_usage(
            [
                {**base, "XML_DATA_ITEM": "ATC_MW", "MW": "1000"},
                {**base, "XML_DATA_ITEM": "ENE_IMPORT_MW", "MW": "800"},
                {**base, "XML_DATA_ITEM": "NEW_ITEM_MW", "TR_TYPE": "X", "LABEL": "New", "MW": "3"},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["atc_mw"], 1000)
        self.assertEqual(rows[0]["ene_import_mw"], 800)
        self.assertIn("NEW_ITEM_MW", rows[0]["extra_json"])


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SP15_DB"] = str(Path(self.tmp.name) / "t.sqlite")
        conn = connect(write=True)
        try:
            with conn:
                upsert(
                    conn,
                    "dam_lmp",
                    [
                        _lmp(HUB, "LMP", 40.0),
                        _lmp(HUB, "MCC", 5.0),
                        _lmp(HUB, "MCE", 34.0),
                        _lmp(HUB, "MCL", 1.0),
                        _lmp(HUB, "MGHG", 0.0),
                        _lmp("DLAP_SCE-APND", "LMP", 41.0),
                        _lmp("DLAP_SCE-APND", "MCC", 6.0),
                    ],
                )
                upsert(
                    conn,
                    "as_price",
                    [
                        {
                            "interval_start": "2026-11-07T08:00:00-00:00",
                            "interval_end": "2026-11-07T09:00:00-00:00",
                            "opr_dt": "2026-11-07",
                            "opr_hr": 1,
                            "anc_type": "RU",
                            "anc_region": "AS_SP26",
                            "xml_data_item": "RU_CLR_PRC",
                            "value": 2.5,
                        }
                    ],
                )
                upsert(
                    conn,
                    "nomogram_shadow",
                    [
                        {
                            "interval_start": "2026-11-07T08:00:00-00:00",
                            "interval_end": "2026-11-07T09:00:00-00:00",
                            "opr_dt": "2026-11-07",
                            "opr_hr": 1,
                            "nomogram_id": "30060_MIDWAY  _500_24156_VINCENT _500_BR_1 _3",
                            "constraint_cause": "Base Case",
                            "value": 12.0,
                            "region_tag": "sp15",
                        }
                    ],
                )
                upsert(
                    conn,
                    "tie_atc",
                    [
                        {
                            "interval_start": "2026-11-07T08:00:00-00:00",
                            "interval_end": "2026-11-07T09:00:00-00:00",
                            "opr_dt": "2026-11-07",
                            "opr_hr": 1,
                            "ti_id": "PALOVRDE_ITC",
                            "ti_direction": "I",
                            "value": 1000.0,
                        }
                    ],
                )
                upsert(
                    conn,
                    "tie_usage",
                    [
                        {
                            "interval_start": "2026-11-07T08:00:00-00:00",
                            "interval_end": "2026-11-07T09:00:00-00:00",
                            "opr_dt": "2026-11-07",
                            "opr_hr": 1,
                            "ti_id": "PALOVRDE_ITC",
                            "ti_direction": "I",
                            "ene_import_mw": 800.0,
                        }
                    ],
                )
        finally:
            conn.close()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("SP15_DB", None)

    def test_training_panel_joins_price_and_the_path_26_boundary(self):
        page = training_panel("2026-11-07", "2026-11-07", ties="PALOVRDE_ITC", limit=10)
        self.assertEqual(page["meta"]["rows_total"], 1)
        row = page["rows"][0]
        self.assertEqual(row["sp15_lmp"], 40.0)
        self.assertEqual(row["sp15_mcc"], 5.0)
        self.assertEqual(row["sce_lmp"], 41.0)
        self.assertEqual(row["as_sp26_ru"], 2.5)
        self.assertEqual(row["path26_shadow"], 12.0)
        self.assertIsNone(row["path15_shadow"])
        self.assertEqual(row["palovrde_atc_i"], 1000.0)
        self.assertEqual(row["palovrde_ene_i"], 800.0)
        self.assertIsNone(row["palovrde_atc_e"])

    def test_sql_tool_is_read_only(self):
        page = query_sql(
            "SELECT value FROM dam_lmp WHERE node = 'TH_SP15_GEN-APND' AND lmp_type = 'LMP'"
        )
        self.assertEqual(page["rows"][0]["value"], 40.0)
        with self.assertRaises(ValueError):
            query_sql("DELETE FROM dam_lmp")
        with self.assertRaises(ValueError):
            query_sql("SELECT no_such_column FROM dam_lmp")


def _lmp(node: str, lmp_type: str, value: float) -> dict:
    return {
        "interval_start": "2026-11-07T08:00:00-00:00",
        "interval_end": "2026-11-07T09:00:00-00:00",
        "opr_dt": "2026-11-07",
        "opr_hr": 1,
        "node": node,
        "lmp_type": lmp_type,
        "xml_data_item": f"{lmp_type}_PRC",
        "value": value,
    }


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SP15_DB"] = str(Path(self.tmp.name) / "sp15.sqlite")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("SP15_DB", None)

    def test_a_full_day_has_no_gaps(self):
        _fill_day("2026-11-07", 24)
        self.assertEqual(day_gaps(date(2026, 11, 7)), [])

    def test_a_short_price_hour_is_reported(self):
        _fill_day("2026-11-07", 24, lmp_hours=23)
        gaps = day_gaps(date(2026, 11, 7))
        self.assertEqual(len(gaps), 1)
        self.assertIn("日前电价 23/24", gaps[0])

    def test_may_source_hole_does_not_require_ties(self):
        _fill_day("2026-05-01", 24, ties=False)
        self.assertEqual(day_gaps(date(2026, 5, 1)), [])


class WatchTests(unittest.TestCase):
    def test_retries_until_the_day_is_complete(self):
        shanghai = ZoneInfo("Asia/Shanghai")
        state = {"n": 0, "now": datetime(2026, 11, 9, 1, 16, tzinfo=shanghai)}
        notes: list[str] = []

        def sync() -> None:
            state["n"] += 1

        def gaps(_day):
            return ["没有联络线 ATC"] if state["n"] < 2 else []

        def sleeper(seconds: float) -> None:
            state["now"] = state["now"] + timedelta(seconds=seconds)

        code = run_watch(
            sync=sync,
            gaps_for=gaps,
            notify=notes.append,
            clock=lambda: state["now"],
            sleeper=sleeper,
        )
        self.assertEqual(code, 0)
        self.assertEqual(state["n"], 2)
        self.assertIn("采集不全", notes[0])
        self.assertIn("已补齐", notes[1])

    def test_stops_at_the_deadline_when_still_short(self):
        shanghai = ZoneInfo("Asia/Shanghai")
        state = {"now": datetime(2026, 11, 9, 1, 50, tzinfo=shanghai)}
        notes: list[str] = []

        def sleeper(seconds: float) -> None:
            state["now"] = state["now"] + timedelta(seconds=seconds)

        code = run_watch(
            pause_seconds=600,
            sync=lambda: None,
            gaps_for=lambda _day: ["没有日前电价"],
            notify=notes.append,
            clock=lambda: state["now"],
            sleeper=sleeper,
        )
        self.assertEqual(code, 1)
        self.assertTrue(any("仍未采全" in note for note in notes))


def _fill_day(day: str, hours: int, *, lmp_hours: int | None = None, ties: bool = True) -> None:
    lmp_hours = hours if lmp_hours is None else lmp_hours
    conn = connect(write=True)
    try:
        lmp_rows = []
        price_rows = []
        requirement_rows = []
        atc_rows = []
        usage_rows = []
        for hour in range(1, hours + 1):
            start = f"{day}T{hour:02d}:00:00Z"
            end = f"{day}T{hour:02d}:59:00Z"
            if hour <= lmp_hours:
                for node in node_ids():
                    for kind in LMP_TYPES:
                        lmp_rows.append(
                            {
                                "interval_start": start,
                                "interval_end": end,
                                "opr_dt": day,
                                "opr_hr": hour,
                                "node": node,
                                "lmp_type": kind,
                                "xml_data_item": f"{kind}_PRC",
                                "value": 1.0,
                            }
                        )
            for kind in AS_TYPES:
                price_rows.append(
                    {
                        "interval_start": start,
                        "interval_end": end,
                        "opr_dt": day,
                        "opr_hr": hour,
                        "anc_type": kind,
                        "anc_region": "AS_SP26",
                        "xml_data_item": f"{kind}_CLR_PRC",
                        "value": 1.0,
                    }
                )
            for anc_type, item in AS_REQUIREMENTS:
                requirement_rows.append(
                    {
                        "interval_start": start,
                        "interval_end": end,
                        "opr_dt": day,
                        "opr_hr": hour,
                        "anc_type": anc_type,
                        "anc_region": "AS_SP26",
                        "xml_data_item": item,
                        "label": item,
                        "value": 1.0,
                    }
                )
            if ties:
                for tie in tie_ids():
                    for direction in TIE_DIRECTIONS:
                        atc_rows.append(
                            {
                                "interval_start": start,
                                "interval_end": end,
                                "opr_dt": day,
                                "opr_hr": hour,
                                "ti_id": tie,
                                "ti_direction": direction,
                                "value": 1.0,
                            }
                        )
                        usage_rows.append(
                            {
                                "interval_start": start,
                                "interval_end": end,
                                "opr_dt": day,
                                "opr_hr": hour,
                                "ti_id": tie,
                                "ti_direction": direction,
                            }
                        )
        with conn:
            upsert(conn, "dam_lmp", lmp_rows)
            upsert(conn, "as_price", price_rows)
            upsert(conn, "as_requirement", requirement_rows)
            upsert(conn, "tie_atc", atc_rows)
            upsert(conn, "tie_usage", usage_rows)
    finally:
        conn.close()


if __name__ == "__main__":
    unittest.main()

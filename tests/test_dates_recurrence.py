"""Comprehensive tests for due dates, hide dates, and recurrence scenarios.

Covers:
- Due date: absolute, relative (+X/-X), clearing, edge cases
- Hide date: absolute, relative to due (-X), relative to today (+X), clearing
- Combined due + hide interactions
- Recurrence: all modes with due/hide propagation
- Modify: changing due/hide on normal and recurring tasks
- Filtering: overdue, today, hidden views with date-based tasks
- Edge cases: no due with hide, clear due retaining hide, etc.
"""

import tempfile
import pytest
import mock
from click.testing import CliRunner
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from src.mytcli.myt import add, modify, delete, done, revert, start, view, admin
from src.mytcli.utils import (
    convert_date, convert_date_rel, is_date_short_format,
    adjust_date, calc_next_inst_date, parse_n_validate_recur,
)
from src.mytcli.constants import (
    CLR_STR, FMT_DATEONLY, SUCCESS, FAILURE,
    MODE_DAILY, MODE_WEEKLY, MODE_MONTHLY, MODE_YEARLY,
    MODE_WKDAY, MODE_MTHDYS, MODE_MONTHS,
)

runner = CliRunner()


@pytest.fixture(scope='module')
def db_path():
    return tempfile.mkdtemp() + "/test_dates.sqlite3"


@pytest.fixture(autouse=True, scope='module')
def init_db(db_path):
    with mock.patch('builtins.input', return_value="yes"):
        runner.invoke(admin, ['--reinit', '-db', db_path])


def _add(db_path, args):
    result = runner.invoke(add, args + ['-db', db_path])
    return result


def _get_id(result):
    return result.output.replace("\n", " ").split(" ")[3]


def _cleanup(db_path, tag):
    with mock.patch('builtins.input', return_value="all"):
        runner.invoke(delete, ['tg:' + tag, '-db', db_path])


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS: convert_date
# ═══════════════════════════════════════════════════════════════════════

class TestConvertDate:
    """Unit tests for convert_date()."""

    def test_absolute_date(self):
        assert convert_date("2024-06-15") == "2024-06-15"

    def test_relative_plus(self):
        expected = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        assert convert_date("+5") == expected

    def test_relative_minus(self):
        expected = (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)
        assert convert_date("-3") == expected

    def test_relative_zero_plus(self):
        expected = date.today().strftime(FMT_DATEONLY)
        assert convert_date("+0") == expected

    def test_relative_zero_minus(self):
        expected = date.today().strftime(FMT_DATEONLY)
        assert convert_date("-0") == expected

    def test_bare_plus_sign(self):
        """A bare '+' with no number should default to +0 (today)."""
        expected = date.today().strftime(FMT_DATEONLY)
        assert convert_date("+") == expected

    def test_bare_minus_sign(self):
        """A bare '-' with no number should default to -0 (today)."""
        expected = date.today().strftime(FMT_DATEONLY)
        assert convert_date("-") == expected

    def test_clr(self):
        assert convert_date(CLR_STR) == CLR_STR

    def test_none(self):
        assert convert_date(None) is None

    def test_empty_string(self):
        assert convert_date("") is None

    def test_invalid_string(self):
        assert convert_date("notadate") is None

    def test_natural_language_date(self):
        """dateutil can parse 'Jan 1 2025'."""
        result = convert_date("Jan 1 2025")
        assert result == "2025-01-01"

    def test_large_relative_offset(self):
        expected = (date.today() + relativedelta(days=365)).strftime(FMT_DATEONLY)
        assert convert_date("+365") == expected


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS: convert_date_rel (hide date logic)
# ═══════════════════════════════════════════════════════════════════════

class TestConvertDateRel:
    """Unit tests for convert_date_rel() - hide date conversion."""

    def test_minus_relative_to_due(self):
        """'-X' is relative to the due date."""
        due = datetime(2024, 12, 25)
        assert convert_date_rel("-4", due) == "2024-12-21"

    def test_plus_relative_to_today(self):
        """'+X' is relative to today, not due date."""
        due = datetime(2024, 12, 25)
        expected = (date.today() + relativedelta(days=4)).strftime(FMT_DATEONLY)
        assert convert_date_rel("+4", due) == expected

    def test_absolute_date(self):
        due = datetime(2024, 12, 25)
        assert convert_date_rel("2024-12-20", due) == "2024-12-20"

    def test_clr(self):
        due = datetime(2024, 12, 25)
        assert convert_date_rel(CLR_STR, due) == CLR_STR

    def test_none_value(self):
        due = datetime(2024, 12, 25)
        assert convert_date_rel(None, due) is None

    def test_minus_with_no_due(self):
        """'-X' with no due date should return None."""
        result = convert_date_rel("-5", None)
        assert result is None

    def test_plus_with_no_due(self):
        """'+X' works even without a due date (relative to today)."""
        expected = (date.today() + relativedelta(days=3)).strftime(FMT_DATEONLY)
        assert convert_date_rel("+3", None) == expected

    def test_minus_zero_equals_due(self):
        due = datetime(2024, 6, 15)
        assert convert_date_rel("-0", due) == "2024-06-15"

    def test_minus_large_offset(self):
        due = datetime(2024, 6, 15)
        assert convert_date_rel("-30", due) == "2024-05-16"


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS: is_date_short_format
# ═══════════════════════════════════════════════════════════════════════

class TestIsDateShortFormat:

    def test_positive_number(self):
        assert is_date_short_format("+5") is True

    def test_negative_number(self):
        assert is_date_short_format("-3") is True

    def test_zero(self):
        assert is_date_short_format("+0") is True

    def test_bare_plus(self):
        assert is_date_short_format("+") is True

    def test_bare_minus(self):
        assert is_date_short_format("-") is True

    def test_no_sign(self):
        assert is_date_short_format("5") is False

    def test_date_string(self):
        assert is_date_short_format("2024-01-01") is False

    def test_none(self):
        assert is_date_short_format(None) is False

    def test_empty(self):
        assert is_date_short_format("") is False


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS: parse_n_validate_recur
# ═══════════════════════════════════════════════════════════════════════

class TestParseNValidateRecur:

    def test_basic_daily(self):
        ret, mode, when = parse_n_validate_recur("D")
        assert ret == SUCCESS
        assert mode == "D"
        assert when is None

    def test_basic_weekly(self):
        ret, mode, when = parse_n_validate_recur("W")
        assert ret == SUCCESS
        assert mode == "W"

    def test_basic_monthly(self):
        ret, mode, when = parse_n_validate_recur("M")
        assert ret == SUCCESS
        assert mode == "M"

    def test_basic_yearly(self):
        ret, mode, when = parse_n_validate_recur("Y")
        assert ret == SUCCESS
        assert mode == "Y"

    def test_every_n_days(self):
        ret, mode, when = parse_n_validate_recur("DE3")
        assert ret == SUCCESS
        assert mode == "D"
        assert when == "E3"

    def test_every_n_weeks(self):
        ret, mode, when = parse_n_validate_recur("WE2")
        assert ret == SUCCESS
        assert mode == "W"
        assert when == "E2"

    def test_every_n_months(self):
        ret, mode, when = parse_n_validate_recur("ME6")
        assert ret == SUCCESS
        assert mode == "M"
        assert when == "E6"

    def test_every_n_years(self):
        ret, mode, when = parse_n_validate_recur("YE2")
        assert ret == SUCCESS
        assert mode == "Y"
        assert when == "E2"

    def test_weekdays(self):
        ret, mode, when = parse_n_validate_recur("WD1,3,5")
        assert ret == SUCCESS
        assert mode == "WD"
        assert when == "1,3,5"

    def test_monthdays(self):
        ret, mode, when = parse_n_validate_recur("MD1,15,28")
        assert ret == SUCCESS
        assert mode == "MD"
        assert when == "1,15,28"

    def test_months(self):
        ret, mode, when = parse_n_validate_recur("MO3,6,9,12")
        assert ret == SUCCESS
        assert mode == "MO"
        assert when == "3,6,9,12"

    def test_invalid_mode(self):
        ret, mode, when = parse_n_validate_recur("X")
        assert ret == FAILURE

    def test_invalid_weekday_8(self):
        ret, mode, when = parse_n_validate_recur("WD8")
        assert ret == FAILURE

    def test_invalid_monthday_32(self):
        ret, mode, when = parse_n_validate_recur("MD32")
        assert ret == FAILURE

    def test_invalid_month_13(self):
        ret, mode, when = parse_n_validate_recur("MO13")
        assert ret == FAILURE

    def test_weekday_0_invalid(self):
        ret, mode, when = parse_n_validate_recur("WD0")
        assert ret == FAILURE

    def test_extended_no_number(self):
        """DE without a number should fail."""
        ret, mode, when = parse_n_validate_recur("DE")
        assert ret == FAILURE

    def test_extended_non_numeric(self):
        """DEabc should fail."""
        ret, mode, when = parse_n_validate_recur("DEabc")
        assert ret == FAILURE


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS: calc_next_inst_date
# ═══════════════════════════════════════════════════════════════════════

class TestCalcNextInstDate:

    def test_daily(self):
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_DAILY, None, start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 1), date(2024, 1, 2)]

    def test_weekly(self):
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_WEEKLY, None, start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 1), date(2024, 1, 8)]

    def test_monthly(self):
        start_dt = date(2024, 1, 15)
        result = calc_next_inst_date(MODE_MONTHLY, None, start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 15), date(2024, 2, 15)]

    def test_yearly(self):
        start_dt = date(2024, 3, 1)
        result = calc_next_inst_date(MODE_YEARLY, None, start_dt, date(2030, 12, 31))
        assert result == [date(2024, 3, 1), date(2025, 3, 1)]

    def test_every_3_days(self):
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_DAILY, "E3", start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 1), date(2024, 1, 4)]

    def test_every_2_weeks(self):
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_WEEKLY, "E2", start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 1), date(2024, 1, 15)]

    def test_every_2_months(self):
        start_dt = date(2024, 1, 15)
        result = calc_next_inst_date(MODE_MONTHLY, "E2", start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 15), date(2024, 3, 15)]

    def test_weekdays_mon_wed_fri(self):
        # Jan 1 2024 is a Monday
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_WKDAY, "1,3,5", start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 1), date(2024, 1, 3)]

    def test_monthdays_1_15(self):
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_MTHDYS, "1,15", start_dt, date(2024, 12, 31))
        assert result == [date(2024, 1, 1), date(2024, 1, 15)]

    def test_months_mar_sep(self):
        start_dt = date(2024, 3, 15)
        result = calc_next_inst_date(MODE_MONTHS, "3,9", start_dt, date(2025, 12, 31))
        assert result == [date(2024, 3, 15), date(2024, 9, 15)]

    def test_end_date_limits_results(self):
        start_dt = date(2024, 1, 1)
        result = calc_next_inst_date(MODE_DAILY, None, start_dt, date(2024, 1, 1))
        # Only one date should be returned since end_dt == start_dt
        assert result == [date(2024, 1, 1)]

    def test_monthly_end_of_month_rollover(self):
        """Monthly recurrence starting Jan 31 - Feb has no 31st so skips to Mar 31.

        NOTE: dateutil rrule MONTHLY skips months that don't have the day.
        Jan 31 -> skips Feb (no 31st) -> Mar 31. This is rrule's default
        behaviour, not a bug, but worth documenting.
        """
        start_dt = date(2024, 1, 31)
        result = calc_next_inst_date(MODE_MONTHLY, None, start_dt, date(2024, 12, 31))
        assert result[0] == date(2024, 1, 31)
        assert result[1] == date(2024, 3, 31)  # Feb skipped (no 31st day)


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Add with due dates
# ═══════════════════════════════════════════════════════════════════════

class TestAddDueDate:

    def test_add_with_absolute_due(self, db_path):
        result = _add(db_path, ['-de', 'Due abs test', '-du', '2025-03-15',
                                '-tg', 'tdu1'])
        assert result.exit_code == 0
        assert "due : 2025-03-15" in result.output
        _cleanup(db_path, 'tdu1')

    def test_add_with_relative_plus_due(self, db_path):
        expected = (date.today() + relativedelta(days=7)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Due +7 test', '-du', '+7', '-tg', 'tdu2'])
        assert result.exit_code == 0
        assert "due : " + expected in result.output
        _cleanup(db_path, 'tdu2')

    def test_add_with_relative_minus_due(self, db_path):
        expected = (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Due -3 test', '-du', '-3', '-tg', 'tdu3'])
        assert result.exit_code == 0
        assert "due : " + expected in result.output
        _cleanup(db_path, 'tdu3')

    def test_add_with_due_today(self, db_path):
        expected = date.today().strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Due today test', '-du', '+0',
                                '-tg', 'tdu4'])
        assert result.exit_code == 0
        assert "due : " + expected in result.output
        _cleanup(db_path, 'tdu4')

    def test_add_without_due(self, db_path):
        result = _add(db_path, ['-de', 'No due test', '-tg', 'tdu5'])
        assert result.exit_code == 0
        assert "due : ..." in result.output
        _cleanup(db_path, 'tdu5')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Add with hide dates
# ═══════════════════════════════════════════════════════════════════════

class TestAddHideDate:

    def test_add_with_absolute_hide(self, db_path):
        result = _add(db_path, ['-de', 'Hide abs test', '-du', '2025-06-15',
                                '-hi', '2025-06-10', '-tg', 'thi1'])
        assert result.exit_code == 0
        assert "hide : 2025-06-10" in result.output
        _cleanup(db_path, 'thi1')

    def test_add_with_hide_minus_relative_to_due(self, db_path):
        """'-5' for hide means due - 5 days."""
        result = _add(db_path, ['-de', 'Hide -5 test', '-du', '2025-06-15',
                                '-hi', '-5', '-tg', 'thi2'])
        assert result.exit_code == 0
        assert "hide : 2025-06-10" in result.output
        _cleanup(db_path, 'thi2')

    def test_add_with_hide_plus_relative_to_today(self, db_path):
        """'+5' for hide means today + 5 days."""
        expected = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Hide +5 test', '-du', '2025-06-15',
                                '-hi', '+5', '-tg', 'thi3'])
        assert result.exit_code == 0
        assert "hide : " + expected in result.output
        _cleanup(db_path, 'thi3')

    def test_add_hide_without_due(self, db_path):
        """Hide with -X and no due date - hide should not be set (no due to reference)."""
        result = _add(db_path, ['-de', 'Hide no due test', '-hi', '-5',
                                '-tg', 'thi4'])
        assert result.exit_code == 0
        # Without a due date, -5 hide should not resolve
        assert "hide : ..." in result.output
        _cleanup(db_path, 'thi4')

    def test_add_hide_plus_without_due(self, db_path):
        """Hide with +X and no due date - should still work (relative to today)."""
        expected = (date.today() + relativedelta(days=3)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Hide +3 no due', '-hi', '+3',
                                '-tg', 'thi5'])
        assert result.exit_code == 0
        assert "hide : " + expected in result.output
        _cleanup(db_path, 'thi5')

    def test_add_hide_same_as_due(self, db_path):
        """Hide -0 means hide = due date."""
        result = _add(db_path, ['-de', 'Hide -0 test', '-du', '2025-06-15',
                                '-hi', '-0', '-tg', 'thi6'])
        assert result.exit_code == 0
        assert "hide : 2025-06-15" in result.output
        _cleanup(db_path, 'thi6')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Modify due dates
# ═══════════════════════════════════════════════════════════════════════

class TestModifyDueDate:

    def _create_task(self, db_path):
        result = _add(db_path, ['-de', 'Modify due test', '-du', '2025-06-15',
                                '-tg', 'tmod'])
        return _get_id(result)

    def test_modify_due_absolute(self, db_path):
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-du', '2025-07-20',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : 2025-07-20" in result.output
        _cleanup(db_path, 'tmod')

    def test_modify_due_relative_plus(self, db_path):
        idn = self._create_task(db_path)
        expected = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        result = runner.invoke(modify, ['id:' + idn, '-du', '+10',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : " + expected in result.output
        _cleanup(db_path, 'tmod')

    def test_modify_due_relative_minus(self, db_path):
        idn = self._create_task(db_path)
        expected = (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)
        result = runner.invoke(modify, ['id:' + idn, '-du', '-2',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : " + expected in result.output
        _cleanup(db_path, 'tmod')

    def test_modify_clear_due(self, db_path):
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-du', 'clr',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : ..." in result.output
        _cleanup(db_path, 'tmod')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Modify hide dates
# ═══════════════════════════════════════════════════════════════════════

class TestModifyHideDate:

    def _create_task(self, db_path):
        result = _add(db_path, ['-de', 'Modify hide test', '-du', '2025-06-15',
                                '-hi', '2025-06-10', '-tg', 'tmhi'])
        return _get_id(result)

    def test_modify_hide_absolute(self, db_path):
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-hi', '2025-06-01',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "hide : 2025-06-01" in result.output
        _cleanup(db_path, 'tmhi')

    def test_modify_hide_minus_relative_to_existing_due(self, db_path):
        """'-3' hide should be relative to the task's existing due date."""
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-hi', '-3',
                                        '-db', db_path])
        assert result.exit_code == 0
        # Due is 2025-06-15, hide = due - 3 = 2025-06-12
        assert "hide : 2025-06-12" in result.output
        _cleanup(db_path, 'tmhi')

    def test_modify_hide_plus_relative_to_today(self, db_path):
        """'+5' hide should be relative to today."""
        idn = self._create_task(db_path)
        expected = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = runner.invoke(modify, ['id:' + idn, '-hi', '+5',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "hide : " + expected in result.output
        _cleanup(db_path, 'tmhi')

    def test_modify_clear_hide(self, db_path):
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-hi', 'clr',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "hide : ..." in result.output
        _cleanup(db_path, 'tmhi')

    def test_modify_due_and_hide_together(self, db_path):
        """Modify both due and hide at the same time. Hide -X should use new due."""
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-du', '2025-08-20',
                                        '-hi', '-5', '-db', db_path])
        assert result.exit_code == 0
        assert "due : 2025-08-20" in result.output
        # Hide should be relative to the NEW due: 2025-08-20 - 5 = 2025-08-15
        assert "hide : 2025-08-15" in result.output
        _cleanup(db_path, 'tmhi')

    def test_modify_hide_minus_after_clearing_due(self, db_path):
        """If due is cleared, -X hide should not resolve."""
        idn = self._create_task(db_path)
        result = runner.invoke(modify, ['id:' + idn, '-du', 'clr',
                                        '-hi', '-3', '-db', db_path])
        assert result.exit_code == 0
        assert "due : ..." in result.output
        # With due cleared, -3 hide should not resolve - hide stays original
        # or is not updated since convert_date_rel returns None when due is None
        _cleanup(db_path, 'tmhi')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Recurring task creation with due dates
# ═══════════════════════════════════════════════════════════════════════

class TestRecurringDue:

    def test_recur_daily_creates_instances(self, db_path):
        duedt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        nextdt = date.today().strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Recur daily', '-re', 'D', '-du', duedt,
                                '-tg', 'trdu1'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        assert "task_type : DERIVED" in result.output
        _cleanup(db_path, 'trdu1')

    def test_recur_weekly_creates_instances(self, db_path):
        duedt = date.today().strftime(FMT_DATEONLY)
        nextdt = (date.today() + relativedelta(days=7)).strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=8)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Recur weekly', '-re', 'W', '-du', duedt,
                                '-en', enddt, '-tg', 'trdu2'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        _cleanup(db_path, 'trdu2')

    def test_recur_monthly_creates_instances(self, db_path):
        duedt = "2024-01-15"
        nextdt = "2024-02-15"
        enddt = "2024-03-01"
        result = _add(db_path, ['-de', 'Recur monthly', '-re', 'M', '-du', duedt,
                                '-en', enddt, '-tg', 'trdu3'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        _cleanup(db_path, 'trdu3')

    def test_recur_no_due_fails(self, db_path):
        result = _add(db_path, ['-de', 'No due recur', '-re', 'D', '-tg', 'trdu4'])
        assert "Need a due date for recurring tasks" in result.output

    def test_recur_end_before_due_fails(self, db_path):
        result = _add(db_path, ['-de', 'Bad end recur', '-re', 'D',
                                '-du', '2025-06-15', '-en', '2025-06-10',
                                '-tg', 'trdu5'])
        assert "End date is less than due date" in result.output


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Recurring task with hide dates
# ═══════════════════════════════════════════════════════════════════════

class TestRecurringHide:

    def test_recur_daily_with_hide_offset(self, db_path):
        """Hide offset should propagate to all derived instances."""
        duedt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        hidedt = (date.today() + relativedelta(days=-4)).strftime(FMT_DATEONLY)
        nextdt = date.today().strftime(FMT_DATEONLY)
        nexthide = (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)
        # hide = due - 3 for first instance
        result = _add(db_path, ['-de', 'Recur hide', '-re', 'D', '-du', duedt,
                                '-hi', '-3', '-tg', 'trhi1'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        # Verify hide is propagated: first hide = due - 3
        assert "hide : " + hidedt in result.output
        _cleanup(db_path, 'trhi1')

    def test_recur_weekly_with_absolute_hide(self, db_path):
        duedt = date.today().strftime(FMT_DATEONLY)
        hidedt = (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=8)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Recur abs hide', '-re', 'W', '-du', duedt,
                                '-hi', hidedt, '-en', enddt, '-tg', 'trhi2'])
        assert result.exit_code == 0
        # First instance should have the specified hide date
        assert "hide : " + hidedt in result.output
        # Second instance (due+7) should have hide = due+7 - 2 = due+5
        nexthide = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        assert "hide : " + nexthide in result.output
        _cleanup(db_path, 'trhi2')

    def test_recur_monthly_with_hide_carries_offset(self, db_path):
        """Monthly recurring: hide offset should be consistent across months."""
        duedt = "2024-01-15"
        enddt = "2024-04-01"
        result = _add(db_path, ['-de', 'Monthly hide', '-re', 'M', '-du', duedt,
                                '-hi', '-5', '-en', enddt, '-tg', 'trhi3'])
        assert result.exit_code == 0
        assert "hide : 2024-01-10" in result.output  # Jan 15 - 5
        assert "hide : 2024-02-10" in result.output  # Feb 15 - 5
        assert "hide : 2024-03-10" in result.output  # Mar 15 - 5
        _cleanup(db_path, 'trhi3')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Extended recurrence modes
# ═══════════════════════════════════════════════════════════════════════

class TestRecurringExtended:

    def test_every_3_days(self, db_path):
        duedt = (date.today() + relativedelta(days=-4)).strftime(FMT_DATEONLY)
        nextdt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        enddt = date.today().strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Every 3 days', '-re', 'DE3', '-du', duedt,
                                '-en', enddt, '-tg', 'trex1'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        assert "recur_when : E3" in result.output
        _cleanup(db_path, 'trex1')

    def test_weekdays_tue_thu(self, db_path):
        # 2024-01-02 is a Tuesday
        duedt = "2024-01-02"
        nextdt = "2024-01-04"  # Thursday
        enddt = "2024-01-05"
        result = _add(db_path, ['-de', 'Tue Thu', '-re', 'WD2,4', '-du', duedt,
                                '-en', enddt, '-tg', 'trex2'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        _cleanup(db_path, 'trex2')

    def test_monthdays_1_and_15(self, db_path):
        duedt = "2024-01-01"
        nextdt = "2024-01-15"
        enddt = "2024-01-16"
        result = _add(db_path, ['-de', '1st and 15th', '-re', 'MD1,15', '-du', duedt,
                                '-en', enddt, '-tg', 'trex3'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        _cleanup(db_path, 'trex3')

    def test_months_jan_jul(self, db_path):
        duedt = "2024-01-10"
        nextdt = "2024-07-10"
        enddt = "2024-08-01"
        result = _add(db_path, ['-de', 'Jan Jul', '-re', 'MO1,7', '-du', duedt,
                                '-en', enddt, '-tg', 'trex4'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        _cleanup(db_path, 'trex4')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: View filters with dates
# ═══════════════════════════════════════════════════════════════════════

class TestViewDateFilters:

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    def test_view_today(self, db_path):
        duedt = date.today().strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Today task', '-du', duedt, '-tg', 'tvf1'])
        _add(db_path, ['-de', 'Future task', '-du', '+10', '-tg', 'tvf1'])
        result = runner.invoke(view, ['TODAY', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tvf1')

    def test_view_overdue(self, db_path):
        duedt = (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Overdue task', '-du', duedt, '-tg', 'tvf2'])
        _add(db_path, ['-de', 'Future task', '-du', '+10', '-tg', 'tvf2'])
        result = runner.invoke(view, ['OVERDUE', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tvf2')

    def test_view_hidden(self, db_path):
        duedt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        hidedt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Hidden task', '-du', duedt, '-hi', hidedt,
             '-tg', 'tvf3'])
        _add(db_path, ['-de', 'Visible task', '-du', '+1', '-tg', 'tvf3'])
        result = runner.invoke(view, ['HIDDEN', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tvf3')

    def test_hidden_not_in_default_view(self, db_path):
        """Hidden tasks should not appear in the default pending view."""
        duedt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        hidedt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Hidden task', '-du', duedt, '-hi', hidedt,
             '-tg', 'tvf4'])
        _add(db_path, ['-de', 'Visible task', '-du', '+1', '-tg', 'tvf4'])
        result = runner.invoke(view, ['-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        assert "Hidden: 1" in result.output
        _cleanup(db_path, 'tvf4')

    def test_task_with_past_hide_is_visible(self, db_path):
        """A task with hide date in the past should be visible."""
        duedt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        hidedt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Was hidden task', '-du', duedt, '-hi', hidedt,
             '-tg', 'tvf5'])
        result = runner.invoke(view, ['-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        assert "Hidden: 0" in result.output
        _cleanup(db_path, 'tvf5')

    def test_overdue_excludes_hidden(self, db_path):
        """Overdue tasks that are hidden should not show in overdue view."""
        duedt = (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)
        hidedt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Hidden overdue', '-du', duedt, '-hi', hidedt,
             '-tg', 'tvf6'])
        result = runner.invoke(view, ['OVERDUE', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 0" in result.output
        assert "Hidden: 1" in result.output
        _cleanup(db_path, 'tvf6')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Due date filters on view/modify
# ═══════════════════════════════════════════════════════════════════════

class TestDueDateFilters:

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    def test_filter_due_eq(self, db_path):
        duedt = date.today().strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'Task A', '-du', duedt, '-tg', 'tdf1'])
        _add(db_path, ['-de', 'Task B', '-du', '+5', '-tg', 'tdf1'])
        result = runner.invoke(view, ['du:eq:+0', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tdf1')

    def test_filter_due_lt(self, db_path):
        _add(db_path, ['-de', 'Past task', '-du', '-5', '-tg', 'tdf2'])
        _add(db_path, ['-de', 'Future task', '-du', '+5', '-tg', 'tdf2'])
        result = runner.invoke(view, ['du:lt:+0', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tdf2')

    def test_filter_due_gt(self, db_path):
        _add(db_path, ['-de', 'Past task', '-du', '-5', '-tg', 'tdf3'])
        _add(db_path, ['-de', 'Future task', '-du', '+5', '-tg', 'tdf3'])
        result = runner.invoke(view, ['du:gt:+0', '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tdf3')

    def test_filter_due_between(self, db_path):
        d1 = (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)
        d2 = date.today().strftime(FMT_DATEONLY)
        d3 = (date.today() + relativedelta(days=2)).strftime(FMT_DATEONLY)
        _add(db_path, ['-de', 'In range', '-du', d2, '-tg', 'tdf4'])
        _add(db_path, ['-de', 'Out range', '-du', '+10', '-tg', 'tdf4'])
        result = runner.invoke(view, ['du:bt:' + d1 + ':' + d3, '-db', db_path])
        assert result.exit_code == 0
        assert "Displayed Tasks: 1" in result.output
        _cleanup(db_path, 'tdf4')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Done/Revert with due and hide
# ═══════════════════════════════════════════════════════════════════════

class TestDoneRevertDates:

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    def test_done_preserves_due_and_hide(self, db_path):
        result = _add(db_path, ['-de', 'Done test', '-du', '2025-06-15',
                                '-hi', '2025-06-10', '-tg', 'tdr1'])
        idn = _get_id(result)
        result = runner.invoke(done, ['id:' + idn, '-db', db_path])
        assert result.exit_code == 0
        assert "due : 2025-06-15" in result.output
        assert "hide : 2025-06-10" in result.output
        _cleanup(db_path, 'tdr1')

    def test_revert_preserves_due_and_hide(self, db_path):
        result = _add(db_path, ['-de', 'Revert test', '-du', '2025-06-15',
                                '-hi', '2025-06-10', '-tg', 'tdr2'])
        idn = _get_id(result)
        result = runner.invoke(done, ['id:' + idn, '-db', db_path])
        temp = result.output.replace("\n", " ")
        uuid_val = temp.split(" ")[3]
        result = runner.invoke(revert, ['COMPLETE', 'uuid:' + uuid_val,
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : 2025-06-15" in result.output
        assert "hide : 2025-06-10" in result.output
        _cleanup(db_path, 'tdr2')


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Modify recurring tasks - due/hide changes
# ═══════════════════════════════════════════════════════════════════════

class TestModifyRecurring:

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    def test_modify_single_recurring_instance_due(self, db_path):
        """Modifying a single recurring instance's due date."""
        duedt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Recur mod', '-re', 'D', '-du', duedt,
                                '-tg', 'trmr1'])
        # Get the first derived task ID
        lines = result.output.split("\n")
        first_id = None
        for line in lines:
            if "Added/Updated Task ID:" in line:
                first_id = line.replace("Added/Updated Task ID:", "").strip().split(" ")[0]
                break
        if first_id:
            with mock.patch('builtins.input', return_value="this"):
                result = runner.invoke(modify, ['id:' + first_id, '-du', '+5',
                                                '-db', db_path])
                assert result.exit_code == 0
        _cleanup(db_path, 'trmr1')

    def test_modify_all_recurring_recurrence_change(self, db_path):
        """Changing recurrence type regenerates all instances."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=30)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Recur change', '-re', 'D', '-du', duedt,
                                '-en', enddt, '-tg', 'trmr2'])
        lines = result.output.split("\n")
        first_id = None
        for line in lines:
            if "Added/Updated Task ID:" in line:
                first_id = line.replace("Added/Updated Task ID:", "").strip().split(" ")[0]
                break
        if first_id:
            with mock.patch('builtins.input', return_value="all"):
                result = runner.invoke(modify, ['id:' + first_id, '-re', 'W',
                                                '-db', db_path])
                assert result.exit_code == 0
                assert "recur_mode : W" in result.output
        _cleanup(db_path, 'trmr2')


# ═══════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    def test_hide_after_due(self, db_path):
        """Hide date after due date is valid (unusual but allowed)."""
        result = _add(db_path, ['-de', 'Hide after due', '-du', '2025-06-15',
                                '-hi', '2025-06-20', '-tg', 'tedge1'])
        assert result.exit_code == 0
        assert "hide : 2025-06-20" in result.output
        _cleanup(db_path, 'tedge1')

    def test_add_with_natural_language_due(self, db_path):
        """Due date as 'Jan 15 2025' should parse correctly."""
        result = _add(db_path, ['-de', 'NL due', '-du', 'Jan 15 2025',
                                '-tg', 'tedge2'])
        assert result.exit_code == 0
        assert "due : 2025-01-15" in result.output
        _cleanup(db_path, 'tedge2')

    def test_modify_add_hide_to_task_without_hide(self, db_path):
        """Add a hide date to a task that originally had none."""
        result = _add(db_path, ['-de', 'No hide', '-du', '2025-06-15',
                                '-tg', 'tedge3'])
        idn = _get_id(result)
        result = runner.invoke(modify, ['id:' + idn, '-hi', '-3', '-db', db_path])
        assert result.exit_code == 0
        assert "hide : 2025-06-12" in result.output
        _cleanup(db_path, 'tedge3')

    def test_modify_add_hide_to_task_without_due(self, db_path):
        """Add hide (-X) to a task with no due: should not set hide."""
        result = _add(db_path, ['-de', 'No due for hide', '-tg', 'tedge4'])
        idn = _get_id(result)
        result = runner.invoke(modify, ['id:' + idn, '-hi', '-3', '-db', db_path])
        assert result.exit_code == 0
        # -3 hide with no due should result in hide not being set
        assert "hide : ..." in result.output
        _cleanup(db_path, 'tedge4')

    def test_recur_every_2_years_far_apart(self, db_path):
        """Every 2 years creates tasks spread far apart."""
        duedt = "2020-01-01"
        nextdt = "2022-01-01"
        enddt = "2022-02-01"
        result = _add(db_path, ['-de', '2yr recur', '-re', 'YE2', '-du', duedt,
                                '-en', enddt, '-tg', 'tedge5'])
        assert result.exit_code == 0
        assert "due : " + duedt in result.output
        assert "due : " + nextdt in result.output
        _cleanup(db_path, 'tedge5')

    def test_recur_monthday_31_skips_short_months(self, db_path):
        """MD31 should only create tasks in months with 31 days."""
        duedt = "2024-01-31"
        enddt = "2024-04-01"
        result = _add(db_path, ['-de', 'Day 31 task', '-re', 'MD31', '-du', duedt,
                                '-en', enddt, '-tg', 'tedge6'])
        assert result.exit_code == 0
        assert "due : 2024-01-31" in result.output
        assert "due : 2024-03-31" in result.output
        # Feb doesn't have 31 days, so there should be no Feb instance
        assert "due : 2024-02-31" not in result.output
        _cleanup(db_path, 'tedge6')

    def test_clear_due_and_hide_together(self, db_path):
        """Clear both due and hide in one modify."""
        result = _add(db_path, ['-de', 'Clear both', '-du', '2025-06-15',
                                '-hi', '2025-06-10', '-tg', 'tedge7'])
        idn = _get_id(result)
        result = runner.invoke(modify, ['id:' + idn, '-du', 'clr', '-hi', 'clr',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : ..." in result.output
        assert "hide : ..." in result.output
        _cleanup(db_path, 'tedge7')

    def test_multiple_due_date_modifications(self, db_path):
        """Modify due date multiple times sequentially."""
        result = _add(db_path, ['-de', 'Multi mod', '-du', '2025-01-01',
                                '-tg', 'tedge8'])
        idn = _get_id(result)
        runner.invoke(modify, ['id:' + idn, '-du', '2025-02-01', '-db', db_path])
        result = runner.invoke(modify, ['id:' + idn, '-du', '2025-03-01',
                                        '-db', db_path])
        assert result.exit_code == 0
        assert "due : 2025-03-01" in result.output
        _cleanup(db_path, 'tedge8')


# ═══════════════════════════════════════════════════════════════════════
# REGRESSION TESTS: Modify hide date scenarios (locks in correct behaviour)
#
# These tests assert the currently-correct scenarios from the hide-date
# analysis table (#3, #5, #8, #9, #11, #12, #13). They exist so that future
# refactors of prep_recurring_tasks / modify_task cannot silently break the
# parts that work today.
# ═══════════════════════════════════════════════════════════════════════

def _extract_first_derived_id(result):
    """Return the id of the first 'Added/Updated Task ID' line."""
    for line in result.output.split("\n"):
        if "Added/Updated Task ID:" in line:
            return (line.replace("Added/Updated Task ID:", "")
                        .strip().split(" ")[0])
    return None


def _id_by_due(output, target_due):
    """Return the id of the block whose 'due :' line equals target_due.

    Recurring add prints derived tasks in an arbitrary order, so tests that
    need to operate on a *specific* instance should look it up by due date.
    """
    for block in _task_blocks(output):
        due_val = None
        idn = None
        for line in block.split("\n"):
            if "Added/Updated Task ID:" in line:
                idn = (line.replace("Added/Updated Task ID:", "")
                           .strip().split(" ")[0])
            stripped = line.strip()
            if stripped.startswith("due :"):
                due_val = stripped.replace("due :", "").strip()
        if due_val == target_due:
            return idn
    return None


def _task_blocks(output):
    """Split modify/add output into per-task blocks keyed on the id line."""
    blocks = []
    current = None
    for line in output.split("\n"):
        if "Added/Updated Task ID:" in line:
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return ["\n".join(b) for b in blocks]


def _due_hide_pairs(output):
    """Return list of (due, hide) pairs from printed task blocks."""
    pairs = []
    for block in _task_blocks(output):
        due = None
        hide = None
        for line in block.split("\n"):
            stripped = line.strip()
            if stripped.startswith("due :"):
                due = stripped.replace("due :", "").strip()
            elif stripped.startswith("hide :"):
                hide = stripped.replace("hide :", "").strip()
        pairs.append((due, hide))
    return pairs


class TestModifyHideRecurringLocked:
    """Lock in the hide-date scenarios that are currently correct."""

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    # ---- Scenario #3: modify-all, due + relative hide together ----
    def test_modify_all_recur_due_and_relhide_together(self, db_path):
        """#3: -du <new> -hi -N on 'all' resolves hide against the NEW due.

        Initial hide offset -4, then change due forward and hide offset to -2;
        every new instance should be (new_due - 2).
        """
        duedt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Du+Hi all', '-re', 'D', '-du', duedt,
                                '-hi', '-4', '-en', enddt, '-tg', 'tlock3'])
        assert result.exit_code == 0
        first_id = _extract_first_derived_id(result)
        assert first_id is not None

        new_due = date.today().strftime(FMT_DATEONLY)
        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + first_id,
                                            '-du', new_due, '-hi', '-2',
                                            '-db', db_path])
        assert result.exit_code == 0
        # Base due = today (new_due). Daily UNTIL_WHEN=2 from today → creates
        # instances with due = today, today+1. Each hide = due - 2.
        exp = [
            (date.today().strftime(FMT_DATEONLY),
             (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)),
            ((date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY),
             (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)),
        ]
        pairs = _due_hide_pairs(result.output)
        # Only inspect DERIVED pairs created by the recreate (skip BASE entry).
        drvd_pairs = [p for p in pairs if p[0] in (exp[0][0], exp[1][0])]
        for due_v, hide_v in exp:
            assert (due_v, hide_v) in drvd_pairs, (
                "Expected derived pair (due={}, hide={}) not found in {}"
                .format(due_v, hide_v, drvd_pairs))
        _cleanup(db_path, 'tlock3')

    # ---- Scenario #5: modify-all, clear hide ----
    def test_modify_all_recur_clear_hide(self, db_path):
        """#5: -hi clr on 'all' removes hide from every new instance.

        Picks today's instance explicitly so the recreated series is
        seeded from today (the modify-all recreate path uses the picked
        derived task's due as the new base due).
        """
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Clr hi all', '-re', 'D', '-du', duedt,
                                '-hi', '-1', '-en', enddt, '-tg', 'tlock5'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', 'clr', '-db', db_path])
        assert result.exit_code == 0
        exp_dues = {
            today_str,
            (date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY),
        }
        recreated = [p for p in _due_hide_pairs(result.output)
                     if p[0] in exp_dues]
        assert len(recreated) == 2, (
            "Expected 2 recreated instances, got {}".format(recreated))
        for due_v, hide_v in recreated:
            assert hide_v == "...", (
                "Expected no hide after clear, got hide={} for due={}"
                .format(hide_v, due_v))
        _cleanup(db_path, 'tlock5')

    # ---- Scenario #8: modify-all, due-only on task with no hide ----
    def test_modify_all_recur_due_only_no_hide_initially(self, db_path):
        """#8: changing due on 'all' when task never had a hide stays no-hide."""
        duedt = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Du only no hi', '-re', 'D',
                                '-du', duedt, '-en', enddt, '-tg', 'tlock8'])
        assert result.exit_code == 0
        first_id = _extract_first_derived_id(result)

        new_due = date.today().strftime(FMT_DATEONLY)
        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + first_id,
                                            '-du', new_due, '-db', db_path])
        assert result.exit_code == 0
        exp_dues = {
            date.today().strftime(FMT_DATEONLY),
            (date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY),
        }
        recreated = [p for p in _due_hide_pairs(result.output)
                     if p[0] in exp_dues]
        assert recreated
        for due_v, hide_v in recreated:
            assert hide_v == "...", (
                "Expected no hide, got hide={} for due={}"
                .format(hide_v, due_v))
        _cleanup(db_path, 'tlock8')

    # ---- Scenario #9: modify-all, add relative hide to task with no hide ----
    def test_modify_all_recur_add_relhide_no_hide_initially(self, db_path):
        """#9: adding -hi -3 via 'all' applies -3 offset to every instance.

        Note: the current modify-all recreate path re-seeds the base due from
        the picked derived task's due. To keep the assertion deterministic
        we pick today's instance explicitly so the recreated series starts
        at today.
        """
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Add hi all', '-re', 'D', '-du', duedt,
                                '-en', enddt, '-tg', 'tlock9'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', '-3', '-db', db_path])
        assert result.exit_code == 0
        exp = [
            (today_str,
             (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)),
            ((date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY),
             (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)),
        ]
        pairs = _due_hide_pairs(result.output)
        recreated = [p for p in pairs if p[0] in (exp[0][0], exp[1][0])]
        for due_v, hide_v in exp:
            assert (due_v, hide_v) in recreated, (
                "Expected (due={}, hide={}) not in {}"
                .format(due_v, hide_v, recreated))
        _cleanup(db_path, 'tlock9')

    # ---- Scenario #11: modify-this, relative hide ----
    def test_modify_this_recur_relative_hide(self, db_path):
        """#11: -hi -2 on a single recurring instance uses that instance's due."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'This hi', '-re', 'D', '-du', duedt,
                                '-hi', '-1', '-en', enddt, '-tg', 'tlock11'])
        assert result.exit_code == 0
        # Pick the instance whose due is today explicitly.
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None, (
            "Could not find derived task with due={}".format(today_str))

        with mock.patch('builtins.input', return_value="this"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', '-2', '-db', db_path])
        assert result.exit_code == 0
        exp_hide = (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)
        pairs = _due_hide_pairs(result.output)
        assert (today_str, exp_hide) in pairs, (
            "Expected ({}, {}) not in {}"
            .format(today_str, exp_hide, pairs))
        _cleanup(db_path, 'tlock11')

    # ---- Scenario #12: modify-this, due + relative hide together ----
    def test_modify_this_recur_due_and_relhide(self, db_path):
        """#12: on a single instance -du +new -hi -N resolves hide against new due."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'This du+hi', '-re', 'D', '-du', duedt,
                                '-hi', '-1', '-en', enddt, '-tg', 'tlock12'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        new_due = (date.today() + relativedelta(days=4)).strftime(FMT_DATEONLY)
        with mock.patch('builtins.input', return_value="this"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', new_due, '-hi', '-2',
                                            '-db', db_path])
        assert result.exit_code == 0
        exp_hide = (date.today() + relativedelta(days=2)).strftime(FMT_DATEONLY)
        pairs = _due_hide_pairs(result.output)
        assert (new_due, exp_hide) in pairs, (
            "Expected ({}, {}) not in {}".format(new_due, exp_hide, pairs))
        _cleanup(db_path, 'tlock12')

    # ---- Scenario #13: modify-this, clear hide ----
    def test_modify_this_recur_clear_hide(self, db_path):
        """#13: -hi clr on a single instance removes hide only from that one."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'This clr hi', '-re', 'D', '-du', duedt,
                                '-hi', '-1', '-en', enddt, '-tg', 'tlock13'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        with mock.patch('builtins.input', return_value="this"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', 'clr', '-db', db_path])
        assert result.exit_code == 0
        pairs = _due_hide_pairs(result.output)
        assert (today_str, "...") in pairs, (
            "Expected cleared hide for today's instance. Pairs: {}"
            .format(pairs))
        _cleanup(db_path, 'tlock13')


# ═══════════════════════════════════════════════════════════════════════
# BUG FIX TESTS: Scenarios #1 and #2 — recreate seeds from base, not
# from whichever derived instance the user filtered on.
# ═══════════════════════════════════════════════════════════════════════

class TestModifyHideRecurringFixed:
    """Scenarios #1 and #2 from the hide-date analysis table."""

    @pytest.fixture(autouse=True)
    def reinit(self, db_path):
        with mock.patch('builtins.input', return_value="yes"):
            runner.invoke(admin, ['--reinit', '-db', db_path])

    # ---- Scenario #1: modify-all due-only preserves hide offset ----
    def test_modify_all_due_only_preserves_hide_offset(self, db_path):
        """#1 (bug fix): changing only due on 'all' keeps original -N offset.

        Before the fix the new hide was derived from
        (picked_derived_old_hide − new_due) which could be an arbitrary
        large negative. Now it should stay at the original offset (-1).
        """
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Due only fix', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix1'])
        assert result.exit_code == 0
        # Pick a non-first instance deliberately (the bug manifested with
        # whichever derived got filtered). Today+1's hide was originally
        # today; after the bug, picking it caused weird offsets.
        tomorrow = (date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, tomorrow)
        assert target_id is not None

        new_due = (date.today() + relativedelta(days=2)).strftime(FMT_DATEONLY)
        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', new_due, '-db', db_path])
        assert result.exit_code == 0
        # After recreation the new base due is today+2. UNTIL_WHEN=2
        # for daily so only today+2 fits ((today+2)-today=2, not < 2);
        # but create_one still yields one instance at the base due.
        # Its hide should preserve the original -1 offset → today+1.
        exp_due = new_due
        exp_hide = (date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY)
        pairs = _due_hide_pairs(result.output)
        recreated = [p for p in pairs if p[0] == exp_due]
        assert recreated, (
            "Expected recreated instance at {}. Pairs: {}"
            .format(exp_due, pairs))
        assert (exp_due, exp_hide) in recreated, (
            "Expected hide={} for due={} (offset -1 preserved). Got: {}"
            .format(exp_hide, exp_due, recreated))
        _cleanup(db_path, 'tfix1')

    def test_modify_all_due_only_preserves_hide_offset_independent_of_pick(
            self, db_path):
        """#1 (bug fix): result is independent of which derived id was picked.

        Run the same modify twice against different picked instances and
        assert the recreated series looks identical.
        """
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        # Run 1: pick today's instance.
        result = _add(db_path, ['-de', 'Pick indep A', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix1a'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_a = _id_by_due(result.output, today_str)
        new_due = (date.today() + relativedelta(days=2)).strftime(FMT_DATEONLY)
        with mock.patch('builtins.input', return_value="all"):
            result_a = runner.invoke(modify, ['id:' + target_a,
                                              '-du', new_due, '-db', db_path])
        recreated_a = [p for p in _due_hide_pairs(result_a.output)
                       if p[0] == new_due]
        _cleanup(db_path, 'tfix1a')

        # Run 2: pick tomorrow's instance, identical everything else.
        result = _add(db_path, ['-de', 'Pick indep B', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix1b'])
        tomorrow = (date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY)
        target_b = _id_by_due(result.output, tomorrow)
        with mock.patch('builtins.input', return_value="all"):
            result_b = runner.invoke(modify, ['id:' + target_b,
                                              '-du', new_due, '-db', db_path])
        recreated_b = [p for p in _due_hide_pairs(result_b.output)
                       if p[0] == new_due]
        _cleanup(db_path, 'tfix1b')

        assert recreated_a == recreated_b, (
            "Recreation result should not depend on picked instance. "
            "A={}, B={}".format(recreated_a, recreated_b))

    # ---- Scenario #2: modify-all hide-only, series starts from base due ----
    def test_modify_all_hide_only_recreates_from_base_due(self, db_path):
        """#2 (bug fix): hide-only 'all' modify recreates from the base's
        original due, so all expected instances are materialised regardless
        of which derived was filtered on."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Hide only fix', '-re', 'D',
                                '-du', duedt, '-en', enddt, '-tg', 'tfix2'])
        assert result.exit_code == 0
        # Deliberately pick tomorrow's instance.
        tomorrow = (date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, tomorrow)
        assert target_id is not None

        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', '-3', '-db', db_path])
        assert result.exit_code == 0
        # Base due is still today (unchanged), so recreation yields both
        # today and today+1 with hide = due - 3 each.
        exp = [
            (date.today().strftime(FMT_DATEONLY),
             (date.today() + relativedelta(days=-3)).strftime(FMT_DATEONLY)),
            ((date.today() + relativedelta(days=1)).strftime(FMT_DATEONLY),
             (date.today() + relativedelta(days=-2)).strftime(FMT_DATEONLY)),
        ]
        pairs = _due_hide_pairs(result.output)
        recreated = [p for p in pairs if p[0] in (exp[0][0], exp[1][0])]
        for pair in exp:
            assert pair in recreated, (
                "Expected {} not in recreated pairs {}"
                .format(pair, recreated))
        _cleanup(db_path, 'tfix2')

    # ---- Scenario #4: reject absolute hide on 'all' recurring modify ----
    def test_modify_all_rejects_absolute_hide(self, db_path):
        """#4: absolute hide date on 'all' recurring should be rejected."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Reject abs hi', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix4a'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)

        far_hide = "2027-01-15"
        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', far_hide, '-db', db_path])
        assert result.exit_code == 0
        # Rich may wrap the message; match a substring that stays on one line.
        normalised = " ".join(result.output.split())
        assert "due-relative offset" in normalised, (
            "Expected rejection message, got: {}".format(result.output))
        _cleanup(db_path, 'tfix4a')

    def test_modify_all_rejects_plus_hide(self, db_path):
        """#4: today-relative '+N' hide on 'all' recurring should be rejected."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Reject +hi', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix4b'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)

        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', '+3', '-db', db_path])
        assert result.exit_code == 0
        # Rich may wrap the message; match a substring that stays on one line.
        normalised = " ".join(result.output.split())
        assert "due-relative offset" in normalised, (
            "Expected rejection message, got: {}".format(result.output))
        _cleanup(db_path, 'tfix4b')

    def test_modify_all_accepts_clr_hide(self, db_path):
        """#4 companion: 'clr' is still accepted for 'all' recurring."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Accept clr', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix4c'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)

        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-hi', 'clr', '-db', db_path])
        assert result.exit_code == 0
        normalised = " ".join(result.output.split())
        assert "due-relative offset" not in normalised
        _cleanup(db_path, 'tfix4c')

    # ---- Scenario #10: modify-this due-only prompts to shift hide ----
    def test_modify_this_due_only_shift_hide_no(self, db_path):
        """#10 default: user answers 'no' → hide stays absolute."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'This du only', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix10a'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None
        # Old hide for today's instance = today - 1.
        old_hide = (date.today() + relativedelta(days=-1)).strftime(FMT_DATEONLY)

        new_due = (date.today() + relativedelta(days=4)).strftime(FMT_DATEONLY)
        # First prompt: this/all/none → 'this'; second prompt: shift? → 'no'.
        with mock.patch('builtins.input', side_effect=["this", "no"]):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', new_due, '-db', db_path])
        assert result.exit_code == 0
        pairs = _due_hide_pairs(result.output)
        assert (new_due, old_hide) in pairs, (
            "Expected hide to remain absolute ({}) after 'no'. Pairs: {}"
            .format(old_hide, pairs))
        _cleanup(db_path, 'tfix10a')

    def test_modify_this_due_only_shift_hide_yes(self, db_path):
        """#10 opt-in: user answers 'yes' → hide shifts by the same delta."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'This du shift', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix10b'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        new_due = (date.today() + relativedelta(days=4)).strftime(FMT_DATEONLY)
        # Old due=today, new due=today+4 → delta +4. Old hide=today-1 →
        # new hide = today+3.
        expected_hide = (date.today()
                         + relativedelta(days=3)).strftime(FMT_DATEONLY)
        with mock.patch('builtins.input', side_effect=["this", "yes"]):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', new_due, '-db', db_path])
        assert result.exit_code == 0
        pairs = _due_hide_pairs(result.output)
        assert (new_due, expected_hide) in pairs, (
            "Expected shifted hide ({}) after 'yes'. Pairs: {}"
            .format(expected_hide, pairs))
        _cleanup(db_path, 'tfix10b')

    def test_modify_this_due_only_no_hide_no_prompt(self, db_path):
        """#10 guard: task without a hide date should not trigger the prompt."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'No hi shift', '-re', 'D',
                                '-du', duedt, '-en', enddt, '-tg', 'tfix10c'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)

        new_due = (date.today() + relativedelta(days=4)).strftime(FMT_DATEONLY)
        # Only 'this' is asked; if the shift prompt were also asked side_effect
        # would be exhausted and raise StopIteration.
        with mock.patch('builtins.input', side_effect=["this"]):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', new_due, '-db', db_path])
        assert result.exit_code == 0
        pairs = _due_hide_pairs(result.output)
        assert (new_due, "...") in pairs, (
            "Expected no-hide instance. Pairs: {}".format(pairs))
        _cleanup(db_path, 'tfix10c')

    def test_modify_this_due_and_hide_explicit_no_prompt(self, db_path):
        """#10 guard: explicit hide passed with due should not trigger prompt."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=10)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Explicit hi', '-re', 'D',
                                '-du', duedt, '-hi', '-1',
                                '-en', enddt, '-tg', 'tfix10d'])
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)

        new_due = (date.today() + relativedelta(days=4)).strftime(FMT_DATEONLY)
        # User explicitly passes -hi -2; shift prompt must not appear.
        with mock.patch('builtins.input', side_effect=["this"]):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', new_due, '-hi', '-2',
                                            '-db', db_path])
        assert result.exit_code == 0
        exp_hide = (date.today() + relativedelta(days=2)).strftime(FMT_DATEONLY)
        pairs = _due_hide_pairs(result.output)
        assert (new_due, exp_hide) in pairs, (
            "Expected explicit hide {}. Pairs: {}".format(exp_hide, pairs))
        _cleanup(db_path, 'tfix10d')

    # ---- Scenario #6: clearing due on recurring task ----
    def test_modify_all_rejects_clear_due(self, db_path):
        """#6: clearing due ('clr') on 'all' recurring must be rejected
        (previously crashed because prep_recurring_tasks strptime(None))."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Clr du rec', '-re', 'D',
                                '-du', duedt, '-en', enddt, '-tg', 'tfix6a'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        with mock.patch('builtins.input', return_value="all"):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', 'clr', '-db', db_path])
        assert result.exit_code == 0
        assert result.exception is None, (
            "Should not crash when clearing due on recurring. "
            "Got: {}".format(result.exception))
        normalised = " ".join(result.output.split())
        assert "Cannot clear due" in normalised, (
            "Expected rejection message, got: {}".format(result.output))
        _cleanup(db_path, 'tfix6a')

    def test_modify_this_clear_due_allowed(self, db_path):
        """#6 companion: clearing due on a single ('this') instance is
        allowed — the series keeps generating further instances."""
        duedt = date.today().strftime(FMT_DATEONLY)
        enddt = (date.today() + relativedelta(days=5)).strftime(FMT_DATEONLY)
        result = _add(db_path, ['-de', 'Clr du this', '-re', 'D',
                                '-du', duedt, '-en', enddt, '-tg', 'tfix6b'])
        assert result.exit_code == 0
        today_str = date.today().strftime(FMT_DATEONLY)
        target_id = _id_by_due(result.output, today_str)
        assert target_id is not None

        with mock.patch('builtins.input', side_effect=["this"]):
            result = runner.invoke(modify, ['id:' + target_id,
                                            '-du', 'clr', '-db', db_path])
        assert result.exit_code == 0
        assert result.exception is None
        _cleanup(db_path, 'tfix6b')

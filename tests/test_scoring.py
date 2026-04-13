"""Tests for calc_task_scores."""

import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from src.mytcli.utils import calc_task_scores
from src.mytcli.constants import (
    PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW, PRIORITY_NORMAL,
    TASK_STATUS_TODO, TASK_STATUS_STARTED,
)


def _make_task(due_days=None, priority=None, status=None,
               now_flag=0, groups=None, notes=None,
               inception_days_ago=1, uuid=None):
    """Build a minimal mock Workspace object for scoring tests."""
    from unittest.mock import MagicMock
    task = MagicMock()
    task.uuid = uuid or "test-uuid-{}-{}".format(due_days, inception_days_ago)
    task.version = 1
    task.now_flag = now_flag
    task.priority = (priority or PRIORITY_NORMAL[0])
    task.status = (status or TASK_STATUS_TODO)
    task.groups = groups
    task.notes = notes
    # incep_diff_now in total seconds
    task.incep_diff_now = inception_days_ago * 86400
    if due_days is None:
        task.due = None
        task.due_diff_today = None
    else:
        task.due = "set"
        task.due_diff_today = due_days
    return task


@pytest.fixture(autouse=True)
def mock_get_tags():
    with patch("src.mytcli.queries.get_tags", return_value=[]):
        yield


class TestDueDateOrdering:
    """Overdue tasks must score higher than today, which must beat future."""

    def _score(self, due_days):
        task = _make_task(due_days=due_days)
        result = calc_task_scores([task])
        return result[task.uuid]

    def test_overdue_beats_today(self):
        assert self._score(-7) > self._score(0)

    def test_today_beats_future(self):
        assert self._score(0) > self._score(7)

    def test_more_overdue_beats_less_overdue(self):
        assert self._score(-14) > self._score(-3)

    def test_sooner_future_beats_later_future(self):
        assert self._score(3) > self._score(30)

    def test_no_due_scores_less_than_due_today(self):
        task_no_due = _make_task(due_days=None)
        task_today = _make_task(due_days=0)
        scores = calc_task_scores([task_no_due, task_today])
        assert scores[task_today.uuid] > scores[task_no_due.uuid]


class TestDueScoreNeverNegative:
    """Due component must never produce a negative score regardless of inputs."""

    def test_far_future_not_negative(self):
        task = _make_task(due_days=365)
        result = calc_task_scores([task])
        assert result[task.uuid] >= 0

    def test_very_overdue_not_negative(self):
        task = _make_task(due_days=-365)
        result = calc_task_scores([task])
        assert result[task.uuid] >= 0


class TestListIndependence:
    """Due score must not change based on what other tasks are present.

    Inception is still list-relative (older tasks score proportionally higher
    within the current view), so we use inception_days_ago=0 for all tasks to
    zero out that component and isolate the due score.
    """

    def test_future_task_score_unchanged_by_companions(self):
        t = _make_task(due_days=7, inception_days_ago=0, uuid="t")
        score_alone = calc_task_scores([t])[t.uuid]

        far = _make_task(due_days=200, inception_days_ago=0, uuid="far")
        score_with_far = calc_task_scores([t, far])[t.uuid]

        assert score_alone == score_with_far

    def test_overdue_task_score_unchanged_by_companions(self):
        t = _make_task(due_days=-3, inception_days_ago=0, uuid="t")
        score_alone = calc_task_scores([t])[t.uuid]

        near = _make_task(due_days=-1, inception_days_ago=0, uuid="near")
        score_with_near = calc_task_scores([t, near])[t.uuid]

        assert score_alone == score_with_near


class TestPriorityOrdering:
    def _score(self, priority):
        task = _make_task(priority=priority)
        result = calc_task_scores([task])
        return result[task.uuid]

    def test_high_beats_medium(self):
        assert self._score(PRIORITY_HIGH[0]) > self._score(PRIORITY_MEDIUM[0])

    def test_medium_beats_normal(self):
        assert self._score(PRIORITY_MEDIUM[0]) > self._score(PRIORITY_NORMAL[0])

    def test_normal_beats_low(self):
        assert self._score(PRIORITY_NORMAL[0]) > self._score(PRIORITY_LOW[0])


class TestInceptionBug:
    """incep_diff_now must use total_seconds, not seconds (0-86399 wrap)."""

    def test_older_task_scores_higher_than_newer(self):
        old = _make_task(inception_days_ago=30)
        new = _make_task(inception_days_ago=1)
        scores = calc_task_scores([old, new])
        assert scores[old.uuid] > scores[new.uuid]

    def test_task_older_than_one_day_scores_higher(self):
        """Regression: with .seconds, a 2-day-old and 0-day-old task could
        have the same incep_diff_now if they share the same time-of-day offset.
        With .total_seconds() this cannot happen."""
        two_days = _make_task(inception_days_ago=2)
        one_day = _make_task(inception_days_ago=1)
        scores = calc_task_scores([two_days, one_day])
        assert scores[two_days.uuid] > scores[one_day.uuid]

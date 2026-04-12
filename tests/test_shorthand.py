"""Tests for the shorthand syntax preprocessor."""

from src.mytcli.shorthand import expand_shorthand


class TestExpandShorthand:
    """Tests for expand_shorthand()."""

    def test_non_setter_command_unchanged(self):
        assert expand_shorthand("view gr:Home") == "view gr:Home"
        assert expand_shorthand("done id:3") == "done id:3"
        assert expand_shorthand("start id:1") == "start id:1"

    def test_empty_input(self):
        assert expand_shorthand("") == ""
        assert expand_shorthand("   ") == ""

    def test_group_shorthand(self):
        result = expand_shorthand('add "Buy milk" +Home')
        assert result == 'add -de "Buy milk" -gr Home'

    def test_context_shorthand(self):
        result = expand_shorthand('add "Buy milk" @errands')
        assert result == 'add -de "Buy milk" -cx errands'

    def test_tag_shorthand(self):
        result = expand_shorthand('add "Buy milk" #shopping')
        assert result == 'add -de "Buy milk" -tg shopping'

    def test_due_shorthand(self):
        result = expand_shorthand('add "Buy milk" ^+7')
        assert result == 'add -de "Buy milk" -du +7'

    def test_priority_shorthand(self):
        result = expand_shorthand('add "Buy milk" !H')
        assert result == 'add -de "Buy milk" -pr H'

    def test_hide_shorthand(self):
        result = expand_shorthand('add "Buy milk" ~+3')
        assert result == 'add -de "Buy milk" -hi +3'

    def test_multiple_shorthand(self):
        result = expand_shorthand('add "Pay bills" +Home.Finance @desk #bills ^tomorrow !H')
        assert "-de" in result
        assert "Pay bills" in result
        assert "-gr Home.Finance" in result
        assert "-cx desk" in result
        assert "-tg bills" in result
        assert "-du tomorrow" in result
        assert "-pr H" in result

    def test_modify_with_shorthand(self):
        result = expand_shorthand("modify id:3 +NewGroup @coding")
        assert "id:3" in result
        assert "-gr NewGroup" in result
        assert "-cx coding" in result

    def test_modify_filters_pass_through(self):
        result = expand_shorthand("modify gr:OldGroup +NewGroup")
        assert "gr:OldGroup" in result
        assert "-gr NewGroup" in result

    def test_standard_flags_pass_through(self):
        result = expand_shorthand('add -de "Test task" -pr H -gr Work')
        assert "-de" in result
        assert "-pr" in result
        assert "-gr" in result

    def test_description_as_quoted_string(self):
        result = expand_shorthand('add "Complete the report" +Work')
        assert "-de" in result
        assert "Complete the report" in result
        assert "-gr Work" in result

    def test_no_shorthand_in_view(self):
        """view command should not expand shorthand."""
        result = expand_shorthand("view +something")
        assert result == "view +something"

    def test_hierarchical_group(self):
        result = expand_shorthand('add "Task" +Work.Backend.API')
        assert "-gr Work.Backend.API" in result

    def test_comma_separated_tags(self):
        result = expand_shorthand('add "Task" #bills,expenses')
        assert "-tg bills,expenses" in result

    def test_date_code_due(self):
        result = expand_shorthand('add "Task" ^2025-12-31')
        assert "-du 2025-12-31" in result

    def test_date_word_due(self):
        result = expand_shorthand('add "Task" ^today')
        assert "-du today" in result

    def test_recur_shorthand_basic(self):
        result = expand_shorthand('add "Pay rent" ^+0 *M')
        assert "-re M" in result
        assert "-en" not in result

    def test_recur_shorthand_with_end(self):
        result = expand_shorthand('add "Standup" ^+0 *WD1,2,5|+30')
        assert "-re WD1,2,5" in result
        assert "-en +30" in result

    def test_recur_shorthand_extended(self):
        result = expand_shorthand('add "Task" ^+0 *MD15|+365')
        assert "-re MD15" in result
        assert "-en +365" in result

    def test_notes_shorthand(self):
        result = expand_shorthand('add "Task" &"remember the expensive brand"')
        assert "-no" in result
        assert "remember the expensive brand" in result

    def test_notes_shorthand_single_word(self):
        result = expand_shorthand('add "Task" &urgent')
        assert "-no urgent" in result

    def test_recur_shorthand_end_only(self):
        result = expand_shorthand("modify id:3 *|+120")
        assert "-en +120" in result
        assert "-re" not in result

    def test_recur_and_notes_combined(self):
        result = expand_shorthand('add "Pay rent" ^+0 +HOME *M|+365 &"check statement"')
        assert "-re M" in result
        assert "-en +365" in result
        assert "-no" in result
        assert "check statement" in result

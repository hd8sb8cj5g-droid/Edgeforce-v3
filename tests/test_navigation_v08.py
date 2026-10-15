"""Static, offline-testable checks for EdgeForce's lazy tabbed UX.

The actual Streamlit headless smoke test runs in GitHub Actions where the
requirements (including Streamlit >=1.55) are installed.
"""
import ast
from pathlib import Path
import re
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT/'app.py').read_text()
TREE = ast.parse(APP)


def _workspace_guard(node, i):
    if not isinstance(node, ast.If):
        return False
    try:
        return (isinstance(node.test, ast.Attribute)
                and node.test.attr == 'open'
                and isinstance(node.test.value, ast.Subscript)
                and isinstance(node.test.value.value, ast.Name)
                and node.test.value.value.id == 'workspace_tabs'
                and node.test.value.slice.value == i)
    except (AttributeError, TypeError):
        return False


def test_streamlit_version_supports_lazy_real_tabs():
    requirements=(ROOT/'requirements.txt').read_text()
    assert 'streamlit>=1.55,<2' in requirements
    assert "st.tabs(TAB_LABELS,key='edgeforce_workspace_tab',on_change='rerun')" in APP
    assert 'page=st.selectbox' not in APP


def test_eight_workspaces_have_real_lazy_tab_guards_and_instructions():
    tabs=[node for node in TREE.body if isinstance(node,ast.If) and any(_workspace_guard(node,i) for i in range(8))]
    assert len(tabs)==8
    assert sorted(node.test.value.slice.value for node in tabs)==list(range(8))
    for i in range(8):
        node=next(n for n in tabs if _workspace_guard(n,i))
        assert len(node.body)==1 and isinstance(node.body[0],ast.With)
        body=node.body[0].body
        assert isinstance(body[0],ast.Expr)
        assert isinstance(body[0].value,ast.Call)
        assert isinstance(body[0].value.func,ast.Name)
        assert body[0].value.func.id=='section_guide'
        guide=body[0].value
        assert len(guide.args[1].elts)==3
        assert all(isinstance(x,ast.Constant) and x.value for x in guide.args[1].elts)
        assert len(body)>=5


def test_sections_preserve_all_core_features():
    for token in [
        'providers.odds_api(', 'providers.odds_event_props(',
        'opportunities.group_game_opportunities(', 'value.scan(',
        'nfl_schedule.prepare_schedule(', 'td_scorers.weekly_scorer_board(',
        'portfolio.optimize_portfolio(', 'opportunities.rank_price_contrarians(',
        'db.log_ticket(', 'db.log_prediction(', 'ledger.performance_rows(',
        'db.backup_bytes(', 'providers.kalshi_markets(',
    ]:
        assert token in APP, token


def test_optional_complex_controls_collapsed_by_default():
    assert "st.expander('⚙️ Advanced EV filters (optional)',expanded=False)" in APP
    assert "st.expander('⚙️ Advanced EV and portfolio settings (optional)',expanded=False)" in APP
    assert "st.expander('📐 Advanced calibration and closing-line metrics',expanded=False)" in APP
    assert "st.expander(f'View detailed +EV table ({len(selected)} offers)',expanded=False)" in APP


def test_instructions_present_in_each_tab_and_render_consistently():
    function=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='section_guide')
    fake=MagicMock()
    module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    ns={'st':fake}
    exec(compile(module,'section_guide','exec'),ns)
    ns['section_guide']('TEST TITLE',['First step','Second step','Third step'],'Caution')
    assert fake.container.called
    markdowns=[args.args[0] for args in fake.markdown.call_args_list]
    assert '### TEST TITLE' in markdowns
    assert '**How to use this section**' in markdowns
    assert '1. First step' in markdowns[2]
    assert '2. Second step' in markdowns[2]
    assert '3. Third step' in markdowns[2]
    fake.caption.assert_called_once_with('Caution')

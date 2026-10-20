"""scripts/fork_sync_check.py 自身的契约测试。

自检脚本是防止"同步后静默丢定制"的闸门, 它本身也必须被测:
真实仓库必须通过; 缺测试文件、缺实现标记时必须报错。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "fork_sync_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fork_sync_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # dataclass 解析注解时需要能通过 sys.modules[cls.__module__] 找到模块。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_repo_passes():
    module = _load_module()
    assert module.run_checks(REPO_ROOT) == []


def test_missing_test_file_is_reported(tmp_path: Path):
    module = _load_module()
    failures = module.run_checks(tmp_path)
    assert any("缺少 fork 回归测试: backend/tests/test_desktop_startup.py" in f for f in failures)


def test_missing_marker_is_reported(tmp_path: Path):
    module = _load_module()
    desktop = tmp_path / "backend" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text("def main():\n    pass\n", encoding="utf-8")

    failures = module.run_checks(tmp_path)
    assert any("实现标记丢失 (桌面启动失败页)" in f for f in failures)


def test_forbidden_marker_is_reported(tmp_path: Path):
    module = _load_module()
    lots = tmp_path / "frontend" / "src" / "custom" / "lots" / "extension.tsx"
    lots.parent.mkdir(parents=True)
    lots.write_text("export default { navigation: [] }\n", encoding="utf-8")

    failures = module.run_checks(tmp_path)
    assert any("不应出现的实现 (持仓提醒导航项" in f for f in failures)


def test_missing_path_is_reported(tmp_path: Path):
    module = _load_module()
    failures = module.run_checks(tmp_path)
    assert any("缺少 fork 模块/扩展注册: backend/app/strategy/price_path.py" in f for f in failures)

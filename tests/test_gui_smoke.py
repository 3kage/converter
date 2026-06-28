import unittest

try:
    import tkinter  # noqa: F401

    from converter.gui_smoke import run_gui_smoke

    _HAS_TK = True
except ImportError:
    _HAS_TK = False


@unittest.skipUnless(_HAS_TK, "tkinter is not available")
class GuiSmokeTests(unittest.TestCase):
    def test_button_helpers_accept_size_overrides(self) -> None:
        run_gui_smoke()


if __name__ == "__main__":
    unittest.main()

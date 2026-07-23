# GUI / desktop app lifecycle (how-to)

Read this when building a desktop or long-running GUI app (Qt/PySide, Tkinter, wxPython, Electron).
It is the build-time companion to `agents/ui/browser.md`'s Desktop GUI path (which is for visual QA).
The principles live in `references/architecture-principles.md` ("Stateful & GUI apps carry an explicit
lifecycle"); this is the mechanics.

## 1. An explicit UI state machine
Model the app's states — e.g. `idle → detecting → scanning → completed | error` — as one enum/state
field, and render from it. Every command that starts long-running work checks the state first and
transitions it. No "implicit" state spread across booleans and widget-enabled flags.

## 2. Guard long-running commands
- A start action (Run, Demo, Scan) is a no-op unless state is idle/ready; disable the action while busy.
- Never create+start a second worker while one is running — that races shared state and external devices.

## 3. Worker lifecycle (Qt/PySide worked example)
- **No signal-name collision** with the thread's own signals. `QThread` already has `finished` — name
  your payload signal differently (e.g. `result(object)` / `failed(str)`), don't shadow `finished`.
- **Connect cleanup.** On finish/error: `worker.deleteLater()`, and clear your reference
  (`self._worker = None`) so a stale handle can't be reused.
- **Cancel on close.** `closeEvent` cancels/awaits every active worker (triage AND any pollers), not
  just one. Provide a cooperative cancel flag the worker checks.
```python
class TriageWorker(QThread):
    result = Signal(object)            # NOT `finished` (QThread owns that)
    failed = Signal(str)
    def __init__(self, flow): super().__init__(); self._flow, self._cancel = flow, False
    def cancel(self): self._cancel = True
    def run(self):
        try: self.result.emit(self._flow.run(should_cancel=lambda: self._cancel))
        except Exception as e: self.failed.emit(str(e))   # prefer a typed error payload
# on start: self._worker = w; w.result.connect(self._done); w.finished.connect(w.deleteLater)
# on done/error: self._worker = None
```

## 4. Coordinate background work
Don't let unrelated pollers run during a scan. Starting a scan suspends the device-detection timer (or
route all device commands through one controller) so background polling can't issue ADB/IO mid-scan.

## 5. Slow I/O off the UI thread
PDF/HTML render, file writes, exports, and any operation that can exceed ~a few hundred ms run in a
worker, not in a GUI slot — a synchronous export freezes the window. Disable the export action while it runs.

## 6. Progress & cancel UX
For anything longer than a moment: a visible progress indicator, **localized** user-facing step labels
(not raw internal step names), busy/disabled controls, and a **cancel** affordance + timeout handling.

## 7. Presenter/controller split
Once the top-level window coordinates workflows + background work + I/O + navigation, move that logic to
a presenter/controller; the widget renders state and forwards intents. A 700-line window owning locale,
polling, workers, export, and navigation is the smell.

## 8. Test the lifecycle
Under `QT_QPA_PLATFORM=offscreen` (or `xvfb`): a second start is rejected while busy; a worker cleans up
on finish/error; `closeEvent` cancels an active worker; export does not block the event loop.

## 9. Drive controls with real events (not slot calls)
QA must prove every control is actually **wired**. Trigger it the way a user would — via `QTest` synthetic
events under `QT_QPA_PLATFORM=offscreen` — then **assert the resulting state transition / signal**, never
by calling the slot directly (a direct slot call still "passes" when the button is connected to nothing).
```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # before any Qt import
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest, QSignalSpy

spy = QSignalSpy(win.connect_btn.clicked)               # or watch the resulting state/model signal
QTest.mouseClick(win.connect_btn, Qt.LeftButton)        # REAL event — not win._on_connect()
pump(200)                                                # drain the loop (NOT time.sleep)
assert win.state == "connecting"                         # the observed transition, not "the slot ran"
assert len(spy) == 1                                     # signal actually fired (control is wired)
```
- **Sweep every nominally-enabled control** — buttons, menu actions reached through their visible menu
  path with mouse/keyboard events, toggles (`QTest.mouseClick` on the checkbox), list rows, dialogs,
  language selectors, save/export, start/stop. Calling `action.trigger()` directly does not prove that
  the action is reachable through the UI.
- A control that, when clicked, emits **no signal and causes no state change** is **unwired → [BLOCKING]**.
- A button **permanently disabled with no reachable state that enables it** is dead UI → **[BLOCKING]**;
  every nominally-enabled button must be reachable from some state, and `isEnabled()` must become `True`
  along a real path (don't force `setEnabled(True)` to make the test pass).
- Keyboard/text entry: `QTest.keyClicks(win.search, "abc")`; assert the model/filter updated.

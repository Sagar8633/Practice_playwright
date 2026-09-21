"""Windows notifications for signals - no account, no quota, no outside service.

This is the "foolproof and free" half of the system. TradingView alerts are
capped by plan and expire; a Windows toast raised by this machine is not capped
by anything, so the whole F&O list can be covered at once.

Nothing here leaves the PC: the toast is built by Windows' own notification API
through PowerShell, and the audit trail is a CSV next to the script. No
Telegram, no webhook, no cloud.
"""
from __future__ import annotations

import csv
import logging
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Sequence
from xml.sax.saxutils import escape

log = logging.getLogger("srk.alerts")

# Toasts must be raised under an AppUserModelID that Windows already knows, or
# they are silently dropped. PowerShell's own registered ID always exists.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_PS_TEMPLATE = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml(@'
{xml}
'@)
$toast = New-Object Windows.UI.Notifications.ToastNotification $doc
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($toast)
"""


def _toast_xml(title: str, lines: Sequence[str], loud: bool) -> str:
    body = "\n".join(escape(x) for x in lines)
    sound = ("<audio src='ms-winsoundevent:Notification.Looping.Alarm2' loop='false'/>"
             if loud else "<audio src='ms-winsoundevent:Notification.Default'/>")
    return (
        "<toast scenario='reminder' duration='long'>"
        "<visual><binding template='ToastGeneric'>"
        f"<text>{escape(title)}</text>"
        f"<text>{body}</text>"
        "</binding></visual>"
        f"{sound}"
        "</toast>"
    )


def toast(title: str, lines: Sequence[str], *, loud: bool = True) -> bool:
    """Raise one Windows notification. Never raises - a failed toast must not
    kill the scan loop, and the console line below is the fallback record."""
    script = _PS_TEMPLATE.format(xml=_toast_xml(title, lines, loud), app_id=APP_ID)
    tmp = Path(tempfile.gettempdir()) / "srk_toast.ps1"
    try:
        tmp.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(tmp)],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            log.error("toast failed: %s", (proc.stderr or "").strip()[:200])
            return False
        return True
    except Exception as exc:                      # noqa: BLE001
        log.error("toast failed: %s", exc)
        return False


class Notifier:
    """Console + toast + CSV, in that order of reliability."""

    def __init__(self, csv_path: Path, *, use_toast: bool = True,
                 max_toasts_per_cycle: int = 6):
        self.csv_path = csv_path
        self.use_toast = use_toast and sys.platform == "win32"
        self.max_toasts = max_toasts_per_cycle
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(
                    ["detected_at", "bar_time", "symbol", "direction",
                     "close", "sl", "adx", "tradingview"])

    def emit(self, signals: List[dict]) -> None:
        """Announce one cycle's signals. Individual toasts name the stock, which
        is the whole point - a bare count tells you nothing you can act on."""
        if not signals:
            return
        now = datetime.now()

        for s in signals:
            print(f"  {s['bar_time']:%d-%b %H:%M}  {s['direction']:<8} "
                  f"{s['symbol']:<12} close {s['close']:>9.2f}  "
                  f"SL {s['sl']:>9.2f}  ADX {s['adx']:>5.1f}")

        with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for s in signals:
                w.writerow([now.isoformat(timespec="seconds"),
                            s["bar_time"].isoformat(timespec="minutes"),
                            s["symbol"], s["direction"], f"{s['close']:.2f}",
                            f"{s['sl']:.2f}", f"{s['adx']:.1f}", s["tradingview"]])

        if not self.use_toast:
            return

        for s in signals[:self.max_toasts]:
            toast(
                f"{s['direction']}  {s['symbol']}",
                [f"15m @ {s['close']:.2f}   SL {s['sl']:.2f}   ADX {s['adx']:.1f}",
                 f"bar {s['bar_time']:%d-%b %H:%M}   {s['tradingview']}"],
                loud=True,
            )
        extra = len(signals) - self.max_toasts
        if extra > 0:
            toast(f"+{extra} more SRK signal(s)",
                  [", ".join(s["symbol"] for s in signals[self.max_toasts:][:12]),
                   f"Full list: {self.csv_path}"], loud=False)

    def heartbeat(self, text: str) -> None:
        if self.use_toast:
            toast("SRK Swing Watcher", [text], loud=False)

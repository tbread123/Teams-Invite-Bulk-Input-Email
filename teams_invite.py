#!/usr/bin/env python3
"""Floating Teams invite typer that stays usable while Teams is focused."""

from __future__ import annotations

import os
import threading
import time

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSButton,
    NSEvent,
    NSEventMaskKeyDown,
    NSFloatingWindowLevel,
    NSFont,
    NSMakeRect,
    NSObject,
    NSPanel,
    NSScreen,
    NSTextField,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorStationary,
)
from Quartz import (
    CGEventCreate,
    CGEventCreateKeyboardEvent,
    CGEventGetLocation,
    CGEventKeyboardSetUnicodeString,
    CGEventPost,
    kCGHIDEventTap,
)
from PyObjCTools import AppHelper

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EMAIL_LIST_PATH = os.path.join(SCRIPT_DIR, "emails.txt")

START_DELAY_SEC = 5
AFTER_EMAIL_SEC = 3.0
AFTER_ENTER_SEC = 0.1
RETURN_KEY = 0x24
F6_KEY = 0x61

try:
    from AppKit import (
        NSWindowStyleMaskClosable,
        NSWindowStyleMaskNonactivatingPanel,
        NSWindowStyleMaskTitled,
        NSWindowStyleMaskUtilityWindow,
    )

    PANEL_STYLE = (
        NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskUtilityWindow
        | NSWindowStyleMaskNonactivatingPanel
    )
except ImportError:
    from AppKit import (
        NSClosableWindowMask,
        NSNonactivatingPanelMask,
        NSTitledWindowMask,
        NSUtilityWindowMask,
    )

    PANEL_STYLE = (
        NSTitledWindowMask
        | NSClosableWindowMask
        | NSUtilityWindowMask
        | NSNonactivatingPanelMask
    )


def load_emails():
    if not os.path.isfile(EMAIL_LIST_PATH):
        raise IOError("Save emails.txt next to teams_invite.py")
    emails = []
    with open(EMAIL_LIST_PATH, "r") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            for part in line.split(","):
                email = part.strip().strip("'\"").strip(",")
                if email:
                    emails.append(email)
    if not emails:
        raise IOError("emails.txt is empty")
    return emails


class AbortRequested(Exception):
    pass


def mouse_in_abort_corner() -> bool:
    loc = CGEventGetLocation(CGEventCreate(None))
    return loc.x <= 8 and loc.y <= 8


def check_abort() -> None:
    if mouse_in_abort_corner():
        raise AbortRequested()


def post_event(event) -> None:
    CGEventPost(kCGHIDEventTap, event)


def type_text(text: str) -> None:
    for ch in text:
        check_abort()
        down = CGEventCreateKeyboardEvent(None, 0, True)
        CGEventKeyboardSetUnicodeString(down, 1, ch)
        post_event(down)
        post_event(CGEventCreateKeyboardEvent(None, 0, False))
        time.sleep(0.015)


def press_enter() -> None:
    check_abort()
    down = CGEventCreateKeyboardEvent(None, RETURN_KEY, True)
    up = CGEventCreateKeyboardEvent(None, RETURN_KEY, False)
    post_event(down)
    post_event(up)


def request_accessibility_prompt() -> None:
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    except Exception:
        pass


def make_label(frame, text, size=13, bold=False):
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
    label.setFont_(font)
    return label


class Controller(NSObject):
    def init(self):
        self = super(Controller, self).init()
        if self is None:
            return None
        self.stop_event = threading.Event()
        self.worker = None
        self.status = None
        self.start_btn = None
        self.stop_btn = None
        self.panel = None
        return self

    def buildPanel(self):
        visible = NSScreen.mainScreen().visibleFrame()
        width, height = 380, 210
        x = visible.origin.x + visible.size.width - width - 24
        y = visible.origin.y + visible.size.height - height - 24
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, width, height),
            PANEL_STYLE,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("Teams Invite Typer")
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setHidesOnDeactivate_(False)
        panel.setFloatingPanel_(True)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setWorksWhenModal_(True)
        panel.setReleasedWhenClosed_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        content = panel.contentView()
        content.addSubview_(
            make_label(
                NSMakeRect(16, 160, 350, 36),
                "Click the Teams email field, then Start or F6.\nEdit emails.txt — it reloads every Start.",
                size=12,
            )
        )

        self.status = make_label(
            NSMakeRect(16, 118, 348, 36),
            "Ready — loading emails.txt…",
            size=12,
            bold=True,
        )
        content.addSubview_(self.status)

        self.start_btn = NSButton.alloc().initWithFrame_(NSMakeRect(16, 54, 160, 44))
        self.start_btn.setTitle_("Start")
        self.start_btn.setBezelStyle_(1)
        self.start_btn.setTarget_(self)
        self.start_btn.setAction_("start:")
        content.addSubview_(self.start_btn)

        self.stop_btn = NSButton.alloc().initWithFrame_(NSMakeRect(196, 54, 160, 44))
        self.stop_btn.setTitle_("Stop")
        self.stop_btn.setBezelStyle_(1)
        self.stop_btn.setTarget_(self)
        self.stop_btn.setAction_("stop:")
        self.stop_btn.setEnabled_(False)
        content.addSubview_(self.stop_btn)

        content.addSubview_(
            make_label(
                NSMakeRect(16, 16, 348, 28),
                "Abort: move mouse to top-left corner.",
                size=11,
            )
        )

        panel.orderFrontRegardless()
        self.panel = panel
        self.refreshStatus_(None)
        from Foundation import NSTimer

        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, "refreshStatus:", None, True
        )
        return panel

    def refreshStatus_(self, timer):
        if self.worker and self.worker.is_alive():
            return
        try:
            count = len(load_emails())
            self.setStatus_("Ready — %d emails from emails.txt" % count)
        except Exception as exc:
            self.setStatus_(str(exc))

    def setStatus_(self, text):
        if self.status is not None:
            self.status.setStringValue_(text)

    def start_(self, sender):
        if self.worker and self.worker.is_alive():
            return
        try:
            emails = load_emails()
        except Exception as exc:
            self.setStatus_(str(exc))
            return
        self.stop_event.clear()
        self.start_btn.setEnabled_(False)
        self.stop_btn.setEnabled_(True)
        self.worker = threading.Thread(
            target=run_typing_job, args=(self, emails), daemon=True
        )
        self.worker.start()

    def stop_(self, sender):
        self.stop_event.set()
        self.setStatus_("Stopping…")

    def finish_(self, info):
        text, error = info
        self.setStatus_(text)
        self.start_btn.setEnabled_(True)
        self.stop_btn.setEnabled_(False)


def run_typing_job(controller, emails):
    try:
        for remaining in range(START_DELAY_SEC, 0, -1):
            if controller.stop_event.is_set() or mouse_in_abort_corner():
                raise AbortRequested()
            AppHelper.callAfter(
                controller.setStatus_,
                "Keep the Teams field focused… %ds" % remaining,
            )
            time.sleep(1)

        for i, email in enumerate(emails):
            if controller.stop_event.is_set():
                raise AbortRequested()
            check_abort()
            AppHelper.callAfter(
                controller.setStatus_,
                "Typing %d/%d: %s" % (i + 1, len(emails), email),
            )
            type_text(email)
            for _ in range(30):
                if controller.stop_event.is_set():
                    raise AbortRequested()
                check_abort()
                time.sleep(AFTER_EMAIL_SEC / 30)
            press_enter()
            time.sleep(AFTER_ENTER_SEC)

        AppHelper.callAfter(controller.finish_, ("Done. Typed %d emails." % len(emails), False))
    except AbortRequested:
        AppHelper.callAfter(
            controller.finish_,
            ("Aborted. Click Start or press F6 to retry.", True),
        )
    except Exception as exc:
        AppHelper.callAfter(controller.finish_, ("Failed: %s" % exc, True))


def main():
    request_accessibility_prompt()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    controller = Controller.alloc().init()
    controller.buildPanel()

    def on_key(event):
        try:
            if event.keyCode() == F6_KEY:
                AppHelper.callAfter(controller.start_, None)
        except Exception:
            pass
        return event

    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_key)
    NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_key)

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()

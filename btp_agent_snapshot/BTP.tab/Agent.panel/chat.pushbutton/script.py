#! python3
# -*- coding: utf-8 -*-

import clr
import System

clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

import base64
import json
import threading
import urllib.request
import urllib.error
import ctypes
from ctypes import wintypes

from System.Windows.Forms import (
    Form,
    FormStartPosition,
    Screen,
    Label,
    TextBox,
    Button,
    OpenFileDialog,
    ScrollBars,
    Clipboard,
    Panel,
    FlowLayoutPanel,
    PictureBox,
    PictureBoxSizeMode,
    Application,
    Padding,
    FlowDirection,
    AutoSizeMode,
    BorderStyle,
    FormBorderStyle,
    FlatStyle,
    Keys
)

from System.Drawing import (
    Point,
    Size,
    Color,
    Font,
    FontStyle,
    Bitmap,
    Rectangle,
    ContentAlignment
)

from System.Drawing.Imaging import ImageFormat
from System.IO import MemoryStream
from System import Enum


# ============================================================
# LOW-LEVEL KEYBOARD HOOK
# ============================================================

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
VK_CONTROL = 0x11
VK_V = 0x56

LRESULT = ctypes.c_ssize_t

HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM
)


class KBDLLHOOKSTRUCT(ctypes.Structure):

    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


user32.SetWindowsHookExW.restype = ctypes.c_void_p

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    ctypes.c_void_p,
    wintypes.DWORD
]

user32.CallNextHookEx.restype = LRESULT

user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM
]

user32.UnhookWindowsHookEx.argtypes = [
    ctypes.c_void_p
]

user32.GetAsyncKeyState.restype = ctypes.c_short


# ============================================================
# SHARED RESPONSE STATE
# ============================================================

shared = {
    "finished": False,
    "answer": None,
    "proposals": []
}


# ============================================================
# CHAT FORM
# ============================================================

class ChatForm(Form):

    def __init__(self):

        Form.__init__(self)

        self.Text = "BTP Assistant"

        self.ClientSize = Size(500, 520)

        self.question = ""

        # ----------------------------------------------------
        # MULTIPLE IMAGE STORAGE
        # ----------------------------------------------------

        self.pending_images = []

        self.submitted = False

        # ====================================================
        # POLISHED CHAT UI
        # ====================================================

        self.BackColor = Color.FromArgb(
            241,
            245,
            249
        )

        self.FormBorderStyle = Enum.ToObject(
            FormBorderStyle,
            4
        )

        self.MaximizeBox = True
        self.MinimizeBox = True

        work_area = Screen.PrimaryScreen.WorkingArea

        sidebar_width = 480
        sidebar_height = work_area.Height

        self.StartPosition = Enum.ToObject(
            FormStartPosition,
            0
        )

        self.Location = Point(
            work_area.Right - sidebar_width,
            work_area.Top
        )

        self.ClientSize = Size(
            sidebar_width,
            sidebar_height
        )

        self.MaximizedBounds = Rectangle(
            work_area.Right - sidebar_width,
            work_area.Top,
            sidebar_width,
            work_area.Height
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        self.header = Panel()

        self.header.Location = Point(
            0,
            0
        )

        self.header.Size = Size(
            560,
            70
        )

        self.header.BackColor = Color.FromArgb(
            16,
            28,
            44
        )

        self.Controls.Add(
            self.header
        )

        self.logo = Label()

        self.logo.Text = "BTP"

        self.logo.TextAlign = Enum.ToObject(
            ContentAlignment,
            32
        )

        self.logo.Location = Point(
            18,
            15
        )

        self.logo.Size = Size(
            40,
            40
        )

        self.logo.BackColor = Color.FromArgb(
            37,
            99,
            168
        )

        self.logo.ForeColor = Color.White

        self.logo.Font = Font(
            "Segoe UI",
            9,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        self.header.Controls.Add(
            self.logo
        )

        self.title_label = Label()

        self.title_label.Text = "BTP Assistant"

        self.title_label.Location = Point(
            70,
            10
        )

        self.title_label.Size = Size(
            280,
            27
        )

        self.title_label.ForeColor = Color.White

        self.title_label.Font = Font(
            "Segoe UI Semibold",
            12,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        self.header.Controls.Add(
            self.title_label
        )

        self.subtitle_label = Label()

        self.subtitle_label.Text = (
            "Your BIM model assistant"
        )

        self.subtitle_label.Location = Point(
            71,
            37
        )

        self.subtitle_label.Size = Size(
            300,
            19
        )

        self.subtitle_label.ForeColor = Color.FromArgb(
            174,
            188,
            207
        )

        self.subtitle_label.Font = Font(
            "Segoe UI",
            8.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        self.header.Controls.Add(
            self.subtitle_label
        )

        self.online_dot = Label()

        self.online_dot.Text = "●"

        self.online_dot.Location = Point(
            505,
            20
        )

        self.online_dot.Size = Size(
            20,
            25
        )

        self.online_dot.ForeColor = Color.FromArgb(
            82,
            205,
            143
        )

        self.online_dot.Font = Font(
            "Segoe UI",
            12,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        self.header.Controls.Add(
            self.online_dot
        )

        self.online_label = Label()

        self.online_label.Text = "Ready"

        self.online_label.Location = Point(
            455,
            40
        )

        self.online_label.Size = Size(
            50,
            18
        )

        self.online_label.ForeColor = Color.FromArgb(
            174,
            188,
            207
        )

        self.online_label.Font = Font(
            "Segoe UI",
            7.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        self.online_label.TextAlign = Enum.ToObject(
            ContentAlignment,
            16
        )

        self.header.Controls.Add(
            self.online_label
        )

        # ----------------------------------------------------
        # CHAT HISTORY
        # ----------------------------------------------------

        self.chat_panel = FlowLayoutPanel()

        self.chat_panel.Location = Point(
            15,
            85
        )

        self.chat_panel.Size = Size(
            530,
            485
        )

        self.chat_panel.AutoScroll = True

        self.chat_panel.FlowDirection = Enum.ToObject(
            FlowDirection,
            1
        )

        self.chat_panel.WrapContents = False

        self.chat_panel.AutoSize = False

        self.chat_panel.BackColor = Color.FromArgb(
            241,
            245,
            249
        )

        self.chat_panel.Padding = Padding(
            16,
            14,
            16,
            14
        )

        self.chat_panel.BorderStyle = Enum.ToObject(
            BorderStyle,
            0
        )

        self.Controls.Add(
            self.chat_panel
        )

        # ----------------------------------------------------
        # INPUT AREA
        # ----------------------------------------------------

        self.input_panel = Panel()

        self.input_panel.Location = Point(
            15,
            580
        )

        self.input_panel.Size = Size(
            530,
            92
        )

        self.input_panel.BackColor = Color.FromArgb(
            255,
            255,
            255
        )

        self.Controls.Add(
            self.input_panel
        )

        self.question_box = TextBox()

        self.question_box.Location = Point(
            0,
            0
        )

        self.question_box.Size = Size(
            530,
            34
        )

        self.question_box.Font = Font(
            "Segoe UI",
            10.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        self.question_box.BackColor = Color.FromArgb(
            255,
            255,
            255
        )

        self.question_box.ForeColor = Color.FromArgb(
            23,
            32,
            51
        )

        self.question_box.BorderStyle = Enum.ToObject(
            BorderStyle,
            0
        )

        self.question_box.KeyDown += (
            self.question_box_key_down
        )

        self.input_panel.Controls.Add(
            self.question_box
        )

        # ----------------------------------------------------
        # ATTACH BUTTON
        # ----------------------------------------------------

        self.attach_button = Button()

        self.attach_button.Text = "Attach Image"

        self.attach_button.Location = Point(
            0,
            46
        )

        self.attach_button.Size = Size(
            132,
            34
        )

        self.attach_button.Font = Font(
            "Segoe UI",
            8.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        self.attach_button.BackColor = Color.FromArgb(
            255,
            255,
            255
        )

        self.attach_button.ForeColor = Color.FromArgb(
            71,
            85,
            105
        )

        self.attach_button.FlatStyle = Enum.ToObject(
            FlatStyle,
            0
        )

        self.attach_button.FlatAppearance.BorderColor = (
            Color.FromArgb(
                203,
                213,
                225
            )
        )

        self.attach_button.Click += (
            self.attach_image
        )

        self.input_panel.Controls.Add(
            self.attach_button
        )

        # ----------------------------------------------------
        # SEND BUTTON
        # ----------------------------------------------------

        self.send_button = Button()

        self.send_button.Text = "Send"

        self.send_button.Location = Point(
            365,
            46
        )

        self.send_button.Size = Size(
            95,
            34
        )

        self.send_button.Font = Font(
            "Segoe UI",
            8.5,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        self.send_button.BackColor = Color.FromArgb(
            37,
            99,
            168
        )

        self.send_button.ForeColor = Color.White

        self.send_button.FlatStyle = Enum.ToObject(
            FlatStyle,
            0
        )

        self.send_button.FlatAppearance.BorderColor = (
            Color.FromArgb(
                37,
                99,
                168
            )
        )

        self.send_button.Click += (
            self.send_question
        )

        self.input_panel.Controls.Add(
            self.send_button
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_label = Label()

        self.status_label.Text = ""

        self.status_label.Location = Point(
            145,
            51
        )

        self.status_label.Size = Size(
            280,
            20
        )

        self.status_label.ForeColor = Color.FromArgb(
            100,
            116,
            139
        )

        self.status_label.Font = Font(
            "Segoe UI",
            8,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        self.status_label.TextAlign = Enum.ToObject(
            ContentAlignment,
            32
        )

        self.input_panel.Controls.Add(
            self.status_label
        )

        # ----------------------------------------------------
        # EMPTY CHAT WELCOME
        # ----------------------------------------------------

        welcome = Panel()

        welcome.Width = 498

        welcome.Height = 118

        welcome.BackColor = Color.FromArgb(
            251,
            252,
            254
        )

        welcome.Margin = Padding(
            0,
            6,
            0,
            14
        )

        welcome_badge = Label()

        welcome_badge.Text = "BTP"

        welcome_badge.TextAlign = Enum.ToObject(
            ContentAlignment,
            32
        )

        welcome_badge.Location = Point(
            12,
            14
        )

        welcome_badge.Size = Size(
            42,
            32
        )

        welcome_badge.BackColor = Color.FromArgb(
            37,
            99,
            168
        )

        welcome_badge.ForeColor = Color.White

        welcome_badge.Font = Font(
            "Segoe UI",
            9,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        welcome.Controls.Add(
            welcome_badge
        )

        welcome_title = Label()

        welcome_title.Text = (
            "Hi! I’m your BIM assistant 👋"
        )

        welcome_title.Location = Point(
            66,
            11
        )

        welcome_title.Size = Size(
            370,
            25
        )

        welcome_title.ForeColor = Color.FromArgb(
            23,
            32,
            51
        )

        welcome_title.Font = Font(
            "Segoe UI Semibold",
            10.5,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        welcome.Controls.Add(
            welcome_title
        )

        welcome_text = Label()

        welcome_text.Text = (
            "Ask about your Revit model, elements, "
            "parameters, quantities, or upload an image."
        )

        welcome_text.Location = Point(
            66,
            38
        )

        welcome_text.Size = Size(
            375,
            48
        )

        welcome_text.ForeColor = Color.FromArgb(
            100,
            116,
            139
        )

        welcome_text.Font = Font(
            "Segoe UI",
            8.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        welcome.Controls.Add(
            welcome_text
        )

        self.chat_panel.Controls.Add(
            welcome
        )

        # ====================================================
        # KEYBOARD HOOK
        # ====================================================

        self._keyboard_hook_id = None

        self._keyboard_hook_proc = HOOKPROC(
            self._low_level_keyboard_callback
        )

        self._install_keyboard_hook()

        self.FormClosing += (
            self._on_form_closing
        )

        self._apply_theme()   # dark theme layer (visual only)


    # ========================================================
    # ENTER KEY → SEND
    # ========================================================

    # ========================================================
    # DARK THEME LAYER - visual only; every existing control and handler is kept
    # ========================================================

    def _apply_theme(self):
        try:
            self._build_theme()
            self._show_fake_selection()
            self.Resize += lambda s, e: self._theme_layout_safe()
        except Exception as ex:
            try:
                self.status_label.Text = "Theme not applied (%s); classic look in use." % ex
            except Exception:
                pass

    def _rgb(self, r, g, b):
        return Color.FromArgb(r, g, b)

    def _round(self, ctrl, r):
        from System.Drawing.Drawing2D import GraphicsPath
        from System.Drawing import Region
        w, h = ctrl.Width, ctrl.Height
        d = 2 * r
        if w <= d or h <= d:
            return
        gp = GraphicsPath()
        gp.AddArc(0, 0, d, d, 180, 90)
        gp.AddArc(w - d - 1, 0, d, d, 270, 90)
        gp.AddArc(w - d - 1, h - d - 1, d, d, 0, 90)
        gp.AddArc(0, h - d - 1, d, d, 90, 90)
        gp.CloseFigure()
        ctrl.Region = Region(gp)

    def _lbl(self, parent, text, x, y, w, h, font, color, align=None):
        from System.Drawing import ContentAlignment
        lb = Label()
        lb.Text = text
        lb.Font = font
        lb.ForeColor = color
        lb.BackColor = Color.Transparent
        lb.AutoSize = False
        lb.Location = Point(x, y)
        lb.Size = Size(w, h)
        lb.TextAlign = align if align is not None else ContentAlignment.MiddleLeft
        parent.Controls.Add(lb)
        return lb

    def _prefill(self, text):
        self.question_box.Text = text
        self.question_box.Focus()
        self.question_box.SelectionStart = len(text)

    def _tile(self, parent, glyph, text, x, y, w, h, prompt):
        from System.Windows.Forms import Cursors
        from System.Drawing import ContentAlignment
        box = Panel()
        box.Location = Point(x, y)
        box.Size = Size(w, h)
        box.BackColor = self.C_TILE
        box.Cursor = Cursors.Hand
        g = self._lbl(box, glyph, 10, 0, 26, h, Font("Segoe MDL2 Assets", 11.0), self.C_TEAL, ContentAlignment.MiddleCenter)
        s = self._lbl(box, text, 36, 0, w - 40, h, Font("Segoe UI", 8.5), self.C_TEXT)
        s.AutoEllipsis = True
        h_ = lambda a, b: self._prefill(prompt)
        for c in (box, g, s):
            c.Cursor = Cursors.Hand
            c.Click += h_
        parent.Controls.Add(box)
        self._round(box, 10)
        return box

    def _nav_click(self, idx, prompt=None):
        for i, (box, g, s) in enumerate(self._nav):
            on = (i == idx)
            box.BackColor = self.C_NAVON if on else self.C_SIDE
            g.ForeColor = self.C_TEAL if on else self.C_MUTED
            s.ForeColor = self.C_TEAL if on else self.C_MUTED
        self._show_view(("chat", "history", "settings")[idx] if 0 <= idx <= 2 else "chat")

    def _show_view(self, name):
        # the chat controls are only hidden, never cleared, so the current conversation is kept
        chat_on = (name == "chat")
        for c in (self.chat_panel, self.input_panel, self.status_label):
            c.Visible = chat_on
        try:
            self._clip_note.Visible = chat_on
        except Exception:
            pass
        self._hist_view.Visible = (name == "history")
        self._set_view.Visible = (name == "settings")
        self._view = name
        try:
            if name == "history" and hasattr(self, "_render_history"):
                self._render_history()
            elif name == "settings" and hasattr(self, "_render_settings"):
                self._render_settings()
        except Exception as ex:
            try:
                self.status_label.Text = "Could not show %s (%s)" % (name, ex)
            except Exception:
                pass

    def _build_theme(self):
        from System.Windows.Forms import Cursors, FlatStyle, FormWindowState
        from System.Drawing import ContentAlignment
        self.C_BG = self._rgb(23, 21, 31)
        self.C_SIDE = self._rgb(28, 25, 38)
        self.C_NAVON = self._rgb(45, 37, 66)
        self.C_CARD = self._rgb(41, 34, 56)
        self.C_TILE = self._rgb(33, 29, 45)
        self.C_LINE = self._rgb(58, 49, 78)
        self.C_TEAL = self._rgb(167, 139, 250)
        self.C_TEALD = self._rgb(167, 139, 250)
        self.C_TEXT = self._rgb(233, 227, 245)
        self.C_MUTED = self._rgb(154, 146, 173)
        self.C_OK = self._rgb(69, 214, 181)
        # palette overrides from theme.json (next to this script); built-in colours are used if it is missing or invalid
        try:
            try:
                _tdir = _os.path.dirname(__file__)
            except NameError:
                _tdir = _os.path.join(_os.environ["APPDATA"], "pyRevit", "Extensions", "btp_agent.extension", "BTP.tab", "Agent.panel", "chat.pushbutton")
            _tp = _os.path.join(_tdir, "theme.json")
            if _os.path.exists(_tp):
                with open(_tp, "r") as _tf:
                    _cfg = json.load(_tf)
                for _k, _v in _cfg.get("colors", {}).items():
                    setattr(self, _k, self._rgb(int(_v[0]), int(_v[1]), int(_v[2])))
                _op = float(_cfg.get("opacity", 1.0))
                if 0.85 <= _op <= 1.0:
                    self.Opacity = _op
        except Exception:
            pass
        work = Screen.PrimaryScreen.WorkingArea
        W = 620
        self.Location = Point(work.Right - W, work.Top)
        self.ClientSize = Size(W, work.Height)
        self.MaximizedBounds = Rectangle(work.Right - W, work.Top, W, work.Height)
        self.BackColor = self.C_BG
        # sidebar
        self._sb = Panel()
        self._sb.BackColor = self.C_SIDE
        self.Controls.Add(self._sb)
        self._nav = []
        items = [(u"\uE8BD", "Chat", None),
                 (u"\uE81C", "Recent", None)]
        for i, (gl, name, prompt) in enumerate(items):
            box = Panel()
            box.Size = Size(56, 58)
            box.Location = Point(4, 84 + i * 66)
            box.Cursor = Cursors.Hand
            g = self._lbl(box, gl, 0, 6, 56, 26, Font("Segoe MDL2 Assets", 15.0), self.C_MUTED, ContentAlignment.MiddleCenter)
            s = self._lbl(box, name, 0, 34, 56, 18, Font("Segoe UI", 7.5), self.C_MUTED, ContentAlignment.MiddleCenter)
            h_ = (lambda k, pr: (lambda a, b: self._nav_click(k, pr)))(i, prompt)
            for c in (box, g, s):
                c.Cursor = Cursors.Hand
                c.Click += h_
            self._sb.Controls.Add(box)
            self._round(box, 10)
            self._nav.append((box, g, s))
        # History and Settings pages (same area as the chat; filled by _render_history / _render_settings)
        self._hist_view = Panel()
        self._hist_view.BackColor = self.C_BG
        self._hist_view.Visible = False
        self._hist_view.AutoScroll = True
        self.Controls.Add(self._hist_view)
        self._set_view = Panel()
        self._set_view.BackColor = self.C_BG
        self._set_view.Visible = False
        self._set_view.AutoScroll = True
        self.Controls.Add(self._set_view)
        self._view = "chat"
        # header (existing controls restyled; anything else in it hidden)
        hd = self.header
        keep = (self.logo, self.title_label, self.subtitle_label, self.online_dot, self.online_label)
        for c in list(hd.Controls):
            if c not in keep:
                c.Visible = False
        for c in keep:
            if c.Parent is not hd:
                hd.Controls.Add(c)
        hd.BackColor = self.C_SIDE
        self.logo.Text = "BTP"
        self.logo.Font = Font("Segoe UI", 10.0, Enum.ToObject(FontStyle, 1))
        self.logo.ForeColor = self.C_BG
        self.logo.BackColor = self.C_TEALD
        self.logo.TextAlign = ContentAlignment.MiddleCenter
        self.logo.Location = Point(16, 14)
        self.logo.Size = Size(42, 42)
        self._round(self.logo, 12)
        self.title_label.Text = "BTP Assistant"
        self.title_label.Font = Font("Segoe UI", 13.0, Enum.ToObject(FontStyle, 1))
        self.title_label.ForeColor = self.C_TEXT
        self.title_label.BackColor = Color.Transparent
        self.title_label.Location = Point(70, 10)
        self.title_label.Size = Size(260, 28)
        self.subtitle_label.Visible = False
        self.online_dot.Text = u"\u25CF"
        self.online_dot.Font = Font("Segoe UI", 8.0)
        self.online_dot.ForeColor = self.C_OK
        self.online_dot.BackColor = Color.Transparent
        self.online_dot.Location = Point(70, 39)
        self.online_dot.Size = Size(14, 18)
        self.online_label.Text = "Online"
        self.online_label.Font = Font("Segoe UI", 9.0)
        self.online_label.ForeColor = self.C_MUTED
        self.online_label.BackColor = Color.Transparent
        self.online_label.TextAlign = ContentAlignment.MiddleLeft
        self.online_label.Location = Point(84, 38)
        self.online_label.Size = Size(160, 20)
        mdl = Font("Segoe MDL2 Assets", 11.0)
        self._h_set = self._lbl(hd, u"\uE713", 0, 21, 32, 28, mdl, self.C_MUTED, ContentAlignment.MiddleCenter)
        self._h_min = self._lbl(hd, u"\uE921", 0, 21, 32, 28, mdl, self.C_MUTED, ContentAlignment.MiddleCenter)
        self._h_cls = self._lbl(hd, u"\uE8BB", 0, 21, 32, 28, mdl, self.C_MUTED, ContentAlignment.MiddleCenter)
        for c in (self._h_set, self._h_min, self._h_cls):
            c.Cursor = Cursors.Hand
        self._h_set.Visible = False   # Settings page removed from the panel
        self._h_min.Click += lambda a, b: self._collapse_to_chip()
        self._h_cls.Click += lambda a, b: self.Close()
        self._h_new = self._lbl(hd, "+ New chat", 0, 22, 86, 26, Font("Segoe UI", 9.0), self.C_TEAL, ContentAlignment.MiddleCenter)
        self._h_new.Cursor = Cursors.Hand
        self._h_new.Click += lambda a, b: self._new_chat()
        # chat area and welcome card
        self.chat_panel.BackColor = self.C_BG
        if self.chat_panel.Controls.Count > 0:
            self.chat_panel.Controls[0].Visible = False
            self._orig_welcome = self.chat_panel.Controls[0]
        self._welcome = Panel()
        self._welcome.BackColor = self.C_CARD
        self.chat_panel.Controls.Add(self._welcome)
        self.chat_panel.Controls.SetChildIndex(self._welcome, 0)
        # input bar
        self.input_panel.BackColor = self.C_CARD
        self.question_box.BackColor = self.C_CARD
        self.question_box.ForeColor = self.C_TEXT
        self.question_box.BorderStyle = Enum.ToObject(BorderStyle, 0)
        self.question_box.Font = Font("Segoe UI", 10.0)
        for b in (self.attach_button, self.send_button):
            b.FlatStyle = FlatStyle.Flat
            b.FlatAppearance.BorderSize = 0
            b.Cursor = Cursors.Hand
        self.attach_button.BackColor = self.C_TILE
        self.attach_button.ForeColor = self.C_MUTED
        # the real Attach button stays working but out of view; a paperclip icon clicks it
        self._clip = self._lbl(self.input_panel, u"\uE723", 10, 12, 40, 40, Font("Segoe MDL2 Assets", 13.0), self.C_MUTED, ContentAlignment.MiddleCenter)
        self._clip.BackColor = self.C_TILE
        self._clip.Cursor = Cursors.Hand
        self._clip.Click += lambda a, b: self.attach_button.PerformClick()
        self._attach_text0 = self.attach_button.Text
        self._clip_note = self._lbl(self, "", 0, 0, 300, 16, Font("Segoe UI", 8.0), self.C_TEAL)
        self._clip_note.BackColor = self.C_BG
        self.attach_button.TextChanged += lambda a, b: setattr(self._clip_note, "Text", "" if self.attach_button.Text == self._attach_text0 else self.attach_button.Text)
        self.send_button.BackColor = self.C_TEAL
        self.send_button.ForeColor = self.C_BG
        if False:
            self.attach_button.Text = u"\uE723"
            self.attach_button.Font = Font("Segoe MDL2 Assets", 13.0)
        if True:
            self.send_button.Text = u"\uE724"
            self.send_button.Font = Font("Segoe MDL2 Assets", 13.0)
        self.status_label.BackColor = self.C_BG
        self.status_label.ForeColor = self.C_MUTED
        self._theme_layout()
        self._nav_click(0, None)
        # restyle every new bubble and card right after the original code draws it
        self.C_UBUB = getattr(self, "C_UBUB", None) or self._rgb(36, 58, 78)
        self.C_WARN = getattr(self, "C_WARN", None) or self._rgb(236, 128, 120)
        for nm, kind in (("append_user_message", "user"), ("append_assistant_message", "assistant"), ("_append_proposal_card", "card")):
            orig = getattr(self, nm)
            def mk(f, k):
                def w(*a, **kw):
                    r = f(*a, **kw)
                    self._restyle_last(k)
                    try:
                        self._record_msg(k, a)
                    except Exception:
                        pass
                    return r
                return w
            setattr(self, nm, mk(orig, kind))
        self._start_new_conv()
        self.FormClosing += lambda s, e: self._save_conv(self._conv)   # save on close too
        # minimise to a chip on the right, loading bubble, retry (flow wrappers only)
        self._load_bounds()
        self.Resize += lambda s, e: self._check_minimize()
        self.VisibleChanged += lambda s, e: self._on_visible()
        self.FormClosing += lambda s, e: self._on_close_extras()
        _u = self.append_user_message
        def _u2(*a, **kw):
            r = _u(*a, **kw)
            if not getattr(self, "_replaying", False):
                try:
                    self._last_question = u"%s" % a[0]
                    self._loading_start()
                except Exception:
                    pass
            return r
        self.append_user_message = _u2
        _cr = self.check_response
        self.check_response = lambda s, e: self._check_with_loading(_cr, s, e)

    def _lum(self, c):
        return 0.299 * c.R + 0.587 * c.G + 0.114 * c.B

    def _restyle_last(self, kind):
        try:
            n = self.chat_panel.Controls.Count
            if n == 0:
                return
            root = self.chat_panel.Controls[n - 1]
            if kind == "card":
                self._restyle_card(root)
            else:
                root.BackColor = self.C_BG
                self._restyle_tree(root, kind)
        except Exception:
            pass

    def _restyle_tree(self, ctrl, kind):
        for c in list(ctrl.Controls):
            bc, fc = c.BackColor, c.ForeColor
            txt = (c.Text or "").strip()
            if bc.A != 0:
                if bc.B > bc.R + 60 and txt == "BTP":
                    c.BackColor = self.C_TEAL
                    c.ForeColor = self.C_BG
                    self._restyle_tree(c, kind)
                    continue
                elif bc.B > bc.R + 60:
                    c.BackColor = self.C_UBUB
                elif self._lum(bc) > 200:
                    c.BackColor = self.C_BG if kind == "user" else self.C_CARD
            if txt == "You":
                c.ForeColor = self.C_MUTED
            elif self._lum(fc) < 110 or (fc.R > 230 and fc.G > 230 and fc.B > 230):
                c.ForeColor = self.C_TEXT
            elif self._lum(fc) < 200:
                c.ForeColor = self.C_MUTED
            self._restyle_tree(c, kind)

    def _restyle_card(self, root):
        from System.Windows.Forms import FlatStyle, Button
        root.BackColor = self.C_CARD
        for c in list(root.Controls):
            if isinstance(c, Button):
                c.FlatStyle = FlatStyle.Flat
                if (c.Text or "") == "Confirm":
                    c.Text = "Apply"
                    c.BackColor = self.C_TEAL
                    c.ForeColor = self.C_BG
                    c.FlatAppearance.BorderSize = 0
                elif (c.Text or "") == "Reject":
                    c.Text = "Cancel"
                    c.BackColor = self.C_CARD
                    c.ForeColor = self.C_TEXT
                    c.FlatAppearance.BorderColor = self.C_LINE
                    c.FlatAppearance.BorderSize = 1
                continue
            fc = c.ForeColor
            c.BackColor = self.C_CARD
            if fc.R > 150 and fc.G < 80 and fc.B < 80:
                c.ForeColor = self.C_WARN
            elif (c.Text or "").startswith("PROPOSED CHANGE"):
                c.ForeColor = self.C_TEAL
            else:
                c.ForeColor = self.C_TEXT
        try:
            self._add_details(root)
        except Exception:
            pass
        self._round(root, 14)

    def _add_details(self, root):
        import re as _re
        from System.Windows.Forms import Button, FlatStyle, TextBox, ScrollBars, Cursors
        pid = None
        for c in root.Controls:
            m = _re.search(r"\((P-[A-Za-z0-9]+)\)", c.Text or "")
            if m:
                pid = m.group(1)
                break
        p = _PANEL["proposals"].get(pid) if pid else None
        card = _PANEL["cards"].get(pid) if pid else None
        if p is None or card is None:
            return
        items = p.get("items") or []
        conf, st = card["confirm"], card["status"]
        btn = Button()
        btn.Text = "Show Details"
        btn.Location = Point(250, conf.Top)
        btn.Size = Size(110, conf.Height)
        btn.FlatStyle = FlatStyle.Flat
        btn.BackColor = self.C_CARD
        btn.ForeColor = self.C_TEAL
        btn.FlatAppearance.BorderColor = self.C_LINE
        btn.Cursor = Cursors.Hand
        root.Controls.Add(btn)
        st.Location = Point(370, st.Top)
        st.Size = Size(max(60, root.Width - 382), st.Height)
        lines = []
        for it in items:
            if it.get("param_name"):
                lines.append(u"id %s  %s [%s] %s:  '%s' -> '%s'" % (it.get("target_id"), it.get("label"), it.get("scope"), it.get("param_name"), it.get("old"), it.get("new")))
            else:
                lines.append(u"%s [%s]:  '%s' -> '%s'" % (it.get("label"), it.get("scope"), it.get("old"), it.get("new")))
        box = TextBox()
        box.Multiline = True
        box.ReadOnly = True
        box.ScrollBars = ScrollBars.Vertical
        box.Text = u"\r\n".join(lines) if lines else u"(no items)"
        box.BackColor = self.C_TILE
        box.ForeColor = self.C_TEXT
        box.BorderStyle = Enum.ToObject(BorderStyle, 0)
        box.Font = Font("Consolas", 8.5)
        h = min(240, 16 * max(1, len(lines)) + 14)
        base_h = root.Height
        box.Location = Point(12, base_h - 2)
        box.Size = Size(root.Width - 24, h)
        box.Visible = False
        root.Controls.Add(box)
        def toggle(s, e):
            if box.Visible:
                box.Visible = False
                root.Height = base_h
                btn.Text = "Show Details"
            else:
                box.Visible = True
                root.Height = base_h + h + 10
                btn.Text = "Hide Details"
            self._round(root, 14)
        btn.Click += toggle

    def _selection_card(self, sel):
        try:
            self._record_msg("selection", (sel,))
        except Exception:
            pass
        from System.Windows.Forms import Button, FlatStyle, Cursors
        from System.Drawing import ContentAlignment
        n = int(sel.get("count") or 0)
        ids = list(sel.get("ids") or [])
        w = self.chat_panel.ClientSize.Width - 32 - 24
        card = Panel()
        card.BackColor = self.C_CARD
        card.Width = w
        card.Margin = Padding(0, 2, 0, 12)
        self._lbl(card, u"\uE73E", 14, 12, 26, 24, Font("Segoe MDL2 Assets", 12.0), self.C_TEAL, ContentAlignment.MiddleCenter)
        self._lbl(card, "Action Preview", 44, 12, w - 60, 24, Font("Segoe UI", 10.0, Enum.ToObject(FontStyle, 1)), self.C_TEAL)
        rows = [("Action", "Select elements"), ("Category", sel.get("category") or "-"), ("Count", "%d element%s" % (n, "" if n == 1 else "s"))]
        y = 42
        for k, v in rows:
            self._lbl(card, k + ":", 44, y, 80, 20, Font("Segoe UI", 9.0), self.C_MUTED)
            self._lbl(card, v, 124, y, w - 140, 20, Font("Segoe UI", 9.0), self.C_TEXT)
            y += 22
        btn = Button()
        btn.Text = "View in Revit"
        btn.Location = Point(44, y + 6)
        btn.Size = Size(130, 30)
        btn.FlatStyle = FlatStyle.Flat
        btn.BackColor = self.C_TILE
        btn.ForeColor = self.C_TEXT
        btn.FlatAppearance.BorderColor = self.C_LINE
        btn.Cursor = Cursors.Hand
        card.Controls.Add(btn)
        note = self._lbl(card, "The %d element%s selected in the model." % (n, " is" if n == 1 else "s are"), 184, y + 10, w - 200, 22, Font("Segoe UI", 8.5), self.C_MUTED)
        btn.Click += lambda s, e: self._zoom_to(ids, note)
        card.Height = y + 48
        self.chat_panel.Controls.Add(card)
        self._round(card, 14)
        try:
            self.scroll_chat_to_bottom()
        except Exception:
            pass

    def _zoom_to(self, ids, note):
        import threading
        payload = json.dumps({"action": "zoom", "element_ids": [int(i) for i in ids[:2000]]})
        def work():
            url = "http://127.0.0.1:48884/bim-brain/view_action"
            try:
                try:
                    import urllib.request as _u
                    _u.urlopen(_u.Request(url, data=payload.encode("utf-8"), headers={"Content-Type": "application/json"}), timeout=60).read()
                except ImportError:
                    import urllib2 as _u2
                    _u2.urlopen(_u2.Request(url, payload, {"Content-Type": "application/json"}), timeout=60).read()
            except Exception:
                pass
        th = threading.Thread(target=work)
        th.daemon = True
        th.start()
        note.Text = "Zooming to them in Revit..."

    def _show_fake_selection(self):
        # test hook: logs\fake_selection.json draws one Action Preview card, then is deleted
        try:
            fp = _os.path.join(_os.path.dirname(FAKE_PROPOSAL_FILE), "fake_selection.json")
            if _os.path.exists(fp):
                import io as _io
                with _io.open(fp, "r", encoding="utf-8-sig") as f:
                    sel = json.load(f)
                _os.remove(fp)
                self._selection_card(sel)
        except Exception:
            pass

    # ---- conversations (Recent): record, save to %AppData%\BTP\recent.json, new chat, open, delete ----
    def _rc_dir(self):
        d = _os.path.join(_os.environ.get("APPDATA", ""), "BTP")
        if not _os.path.isdir(d):
            _os.makedirs(d)
        return d

    def _now_iso(self):
        import time as _time
        return _time.strftime("%Y-%m-%dT%H:%M:%S")

    def _hist_load(self):
        import io as _io, time as _time
        d = self._rc_dir()
        path = _os.path.join(d, "recent.json")
        src = path if _os.path.exists(path) else _os.path.join(d, "history.json")
        if not _os.path.exists(src):
            return []
        try:
            with _io.open(src, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            convs = data.get("conversations") if isinstance(data, dict) else None
            if not isinstance(convs, list):
                raise ValueError("no conversations list")
            out = []
            for c in convs:
                if isinstance(c, dict) and c.get("id") and c.get("messages"):
                    c.setdefault("createdAt", c.get("created", ""))
                    c.setdefault("updatedAt", c.get("updated", c.get("createdAt", "")))
                    out.append(c)
            return out
        except Exception:
            try:   # keep the unreadable file for inspection; start empty
                _os.rename(src, _os.path.join(d, "recent.corrupt-%d.json" % int(_time.time())))
            except Exception:
                pass
            return []

    def _hist_save_all(self, convs):
        import io as _io
        from System.IO import File
        path = _os.path.join(self._rc_dir(), "recent.json")
        tmp = path + ".tmp"
        with _io.open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps({"version": 2, "conversations": convs}, ensure_ascii=False, indent=1))
        if File.Exists(path):
            File.Replace(tmp, path, None)
        else:
            File.Move(tmp, path)

    def _save_conv(self, conv):
        try:
            if not conv or not conv.get("messages"):
                return   # never save empty chats
            convs = [c for c in self._hist_load() if c.get("id") != conv["id"]]
            convs.append(conv)
            convs.sort(key=lambda c: c.get("updatedAt", ""), reverse=True)
            self._hist_save_all(convs)
        except Exception as ex:
            try:
                self.status_label.Text = "Recent not saved (%s)" % ex
            except Exception:
                pass

    def _start_new_conv(self):
        global BRAIN_SESSION_ID
        import uuid as _uuid
        cid = str(_uuid.uuid4())
        now = self._now_iso()
        self._conv = {"id": cid, "session_id": "revit_btp_" + cid.replace("-", "")[:16], "title": "",
                      "createdAt": now, "updatedAt": now, "messages": []}
        BRAIN_SESSION_ID = self._conv["session_id"]

    def _busy(self):
        try:
            return not self.send_button.Enabled   # disabled while a request is in flight
        except Exception:
            return False

    def _record_msg(self, kind, args):
        if getattr(self, "_replaying", False) or not getattr(self, "_conv", None):
            return
        conv = self._conv
        m = None
        if kind == "user" and args:
            m = {"role": "user", "text": u"%s" % args[0]}
        elif kind == "assistant" and args:
            m = {"role": "assistant", "text": u"%s" % args[0]}
        elif kind == "card" and args:
            pp = args[0] or {}
            items = pp.get("items") or []
            m = {"role": "card", "pid": pp.get("proposal_id"), "description": (pp.get("args") or {}).get("description", ""),
                 "items": items[:200], "count": len(items), "status": "pending"}
        elif kind == "selection" and args:
            ss = args[0] or {}
            m = {"role": "selection", "category": ss.get("category"), "count": ss.get("count"), "ids": list(ss.get("ids") or [])[:2000]}
        if m is None:
            return
        conv["messages"].append(m)
        if m["role"] == "user" and not conv.get("title"):
            tx = m["text"].strip()
            conv["title"] = tx[:60] + (u"..." if len(tx) > 60 else u"")
        conv["updatedAt"] = self._now_iso()
        if m["role"] == "card":
            card = _PANEL["cards"].get(m["pid"])
            if card is not None:
                st = card["status"]
                st.TextChanged += (lambda mm, cc, ll: (lambda s, e: self._card_status(mm, cc, ll)))(m, conv, st)
        self._save_conv(conv)

    def _card_status(self, m, conv, label):
        txt = (label.Text or "").strip()
        if txt and not getattr(self, "_replaying", False):
            m["status"] = txt
            conv["updatedAt"] = self._now_iso()
            self._save_conv(conv)

    def _clear_chat_ui(self):
        keep = (getattr(self, "_welcome", None), getattr(self, "_orig_welcome", None))
        for c in list(self.chat_panel.Controls):
            if not any(c is k for k in keep if k is not None):
                self.chat_panel.Controls.Remove(c)
                try:
                    c.Dispose()
                except Exception:
                    pass
        for pid, pp in list(_PANEL["proposals"].items()):
            if pp.get("_state") == "pending":
                pp["_state"] = "expired"
        shared["proposals"] = []
        shared["selection"] = None
        self.question_box.Text = ""
        self.pending_images = []
        try:
            self.attach_button.Text = self._attach_text0
            self._clip_note.Text = ""
        except Exception:
            pass
        self.status_label.Text = ""

    def _new_chat(self):
        if self._busy():
            self.status_label.Text = "Wait for the current reply to finish, then start a new chat."
            return
        self._save_conv(self._conv)
        self._clear_chat_ui()
        self._start_new_conv()
        self._nav_click(0)

    def _open_conv(self, cid):
        global BRAIN_SESSION_ID
        if self._busy():
            self.status_label.Text = "Wait for the current reply to finish."
            self._nav_click(0)
            return
        if getattr(self, "_conv", None) and self._conv.get("id") == cid:
            self._nav_click(0)
            return
        conv = None
        for c in self._hist_load():
            if c.get("id") == cid:
                conv = c
                break
        if conv is None:
            return
        self._save_conv(self._conv)
        self._clear_chat_ui()
        conv.setdefault("session_id", "revit_btp_" + cid.replace("-", "")[:16])
        self._conv = conv
        BRAIN_SESSION_ID = conv["session_id"]
        self._replaying = True
        try:
            for n, m in enumerate(conv.get("messages") or []):
                try:
                    self._replay(m, n)
                except Exception:
                    pass
        finally:
            self._replaying = False
        self._nav_click(0)

    def _replay(self, m, n):
        r = m.get("role")
        if r == "user":
            self.append_user_message(m.get("text", u""), [])
        elif r == "assistant":
            self.append_assistant_message(m.get("text", u""))
        elif r == "selection":
            self._selection_card({"category": m.get("category"), "count": m.get("count"), "ids": m.get("ids") or []})
        elif r == "card":
            pid = m.get("pid") or ("P-OLD%d" % n)
            p = {"proposal_id": pid, "function": "run_action", "status": "pending",
                 "args": {"description": m.get("description", ""), "code": "", "expected_changes": []},
                 "items": m.get("items") or []}
            self._append_proposal_card(p)
            pp = _PANEL["proposals"].get(pid)
            if pp is not None:
                pp["_state"] = "expired"
            card = _PANEL["cards"].get(pid)
            if card is not None:
                card["confirm"].Enabled = False
                card["reject"].Enabled = False
                st = m.get("status") or ""
                card["status"].Text = st if st in ("Applied", "Not applied", "Rejected") else "Expired - not applicable"

    def _rc_when(self, iso):
        import datetime as _dt
        try:
            d = _dt.datetime.strptime((iso or "").replace(" ", "T")[:16], "%Y-%m-%dT%H:%M")
        except Exception:
            return iso or ""
        today = _dt.date.today()
        hm = d.strftime("%I:%M %p").lstrip("0")
        if d.date() == today:
            return "Today " + hm
        if d.date() == today - _dt.timedelta(days=1):
            return "Yesterday " + hm
        return d.strftime("%d %b %Y")

    def _render_history(self):
        from System.Windows.Forms import TextBox, Cursors
        from System.Drawing import ContentAlignment
        v = self._hist_view
        w = v.ClientSize.Width
        if getattr(self, "_rc_search", None) is None:
            self._lbl(v, "Recent", 20, 14, 200, 28, Font("Segoe UI", 13.0, Enum.ToObject(FontStyle, 1)), self.C_TEXT)
            sb = TextBox()
            sb.Location = Point(20, 50)
            sb.BackColor = self.C_CARD
            sb.ForeColor = self.C_TEXT
            sb.BorderStyle = Enum.ToObject(BorderStyle, 1)
            sb.Font = Font("Segoe UI", 10.0)
            sb.TextChanged += lambda s, e: self._render_history()
            v.Controls.Add(sb)
            self._rc_search = sb
            lst = Panel()
            lst.Location = Point(12, 86)
            lst.AutoScroll = True
            lst.BackColor = self.C_BG
            v.Controls.Add(lst)
            self._rc_list = lst
        self._rc_search.Size = Size(w - 40, 26)
        lst = self._rc_list
        lst.Size = Size(w - 24, max(100, v.ClientSize.Height - 96))
        for c in list(lst.Controls):
            lst.Controls.Remove(c)
            c.Dispose()
        q = (self._rc_search.Text or "").strip().lower()
        convs = [c for c in self._hist_load() if q in (c.get("title") or "").lower()]
        if not convs:
            self._lbl(lst, "No recent chats yet." if not q else "No chats match your search.", 8, 10, lst.Width - 20, 24, Font("Segoe UI", 9.5), self.C_MUTED)
            return
        rw = lst.Width - 26
        active = self._conv.get("id") if getattr(self, "_conv", None) else None
        y = 0
        for c in convs:
            row = Panel()
            row.Location = Point(4, y)
            row.Size = Size(rw, 56)
            row.BackColor = self.C_NAVON if c.get("id") == active else self.C_CARD
            title = (c.get("title") or "(untitled)").strip()
            if len(title) > 40:
                title = title[:40].rstrip() + u"..."
            t1 = self._lbl(row, title, 14, 8, rw - 60, 22, Font("Segoe UI", 9.5, Enum.ToObject(FontStyle, 1)), self.C_TEXT)
            n = len(c.get("messages") or [])
            t2 = self._lbl(row, u"%s  \u00b7  %d message%s" % (self._rc_when(c.get("updatedAt")), n, "" if n == 1 else "s"), 14, 30, rw - 60, 18, Font("Segoe UI", 8.5), self.C_MUTED)
            dl = self._lbl(row, u"\uE74D", rw - 40, 14, 28, 28, Font("Segoe MDL2 Assets", 11.0), self.C_MUTED, ContentAlignment.MiddleCenter)
            cid = c.get("id")
            op = (lambda k: (lambda s, e: self._open_conv(k)))(cid)
            for x in (row, t1, t2):
                x.Cursor = Cursors.Hand
                x.Click += op
            dl.Cursor = Cursors.Hand
            dl.Click += (lambda k, tt: (lambda s, e: self._delete_conv(k, tt)))(cid, title)
            lst.Controls.Add(row)
            self._round(row, 10)
            y += 64

    def _delete_conv(self, cid, title):
        from System.Windows.Forms import MessageBox, MessageBoxButtons, DialogResult
        if MessageBox.Show(u"Delete this chat from Recent?\n\n%s" % title, "BTP Assistant", MessageBoxButtons.YesNo) != DialogResult.Yes:
            return
        self._hist_save_all([c for c in self._hist_load() if c.get("id") != cid])
        if getattr(self, "_conv", None) and self._conv.get("id") == cid:
            self._clear_chat_ui()
            self._start_new_conv()
        self._render_history()

    # ---- minimise to a chip on the RIGHT edge (never the bottom-left) ----
    def _bounds_path(self):
        return _os.path.join(self._rc_dir(), "window.json")

    def _save_bounds(self):
        try:
            from System.Windows.Forms import FormWindowState
            if self.WindowState != FormWindowState.Normal or not self.Visible:
                return
            wa = Screen.FromControl(self).WorkingArea
            if self.Left + self.Width // 2 < wa.Left + wa.Width // 2:
                return   # only right-side positions are remembered
            import io as _io
            with _io.open(self._bounds_path(), "w", encoding="utf-8") as f:
                f.write(json.dumps({"x": self.Left, "y": self.Top, "w": self.Width, "h": self.Height}))
        except Exception:
            pass

    def _load_bounds(self):
        try:
            import io as _io
            bp = self._bounds_path()
            if not _os.path.exists(bp):
                return
            with _io.open(bp, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            x, y, w, h = int(d["x"]), int(d["y"]), int(d["w"]), int(d["h"])
            wa = Screen.PrimaryScreen.WorkingArea
            if w < 360 or h < 300 or x + w // 2 < wa.Left + wa.Width // 2 or x > wa.Right - 100 or y < wa.Top - 10 or y > wa.Bottom - 100:
                return
            self.Location = Point(x, y)
            self.Size = Size(w, h)
        except Exception:
            pass

    def _check_minimize(self):
        from System.Windows.Forms import FormWindowState
        if self.WindowState == FormWindowState.Minimized:
            self.WindowState = FormWindowState.Normal
            self._collapse_to_chip()

    # ---- minimised launcher chip: a small WPF window with true transparency (the chat panel itself is unchanged) ----
    CHIP_XAML = u"""<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent" ShowInTaskbar="False"
        Topmost="False" ResizeMode="NoResize" ShowActivated="False" Width="260" Height="92" Title="BTP Assistant">
  <Grid Margin="16" HorizontalAlignment="Right" VerticalAlignment="Center">
    <Grid.ColumnDefinitions><ColumnDefinition Width="Auto"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
    <Border x:Name="pill" Grid.Column="0" Height="40" CornerRadius="20" Margin="0,0,-24,0" Padding="16,0,34,0"
            VerticalAlignment="Center" Opacity="0" RenderTransformOrigin="1,0.5" IsHitTestVisible="False">
      <Border.RenderTransform><ScaleTransform x:Name="pillScale" ScaleX="0" ScaleY="1"/></Border.RenderTransform>
      <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
        <TextBlock x:Name="pillText" Text="BTP Assistant" FontFamily="Segoe UI" FontSize="12.5" FontWeight="SemiBold" VerticalAlignment="Center"/>
        <TextBlock x:Name="pillChev" Text="&#x2039;" Margin="8,0,0,1" FontSize="15" VerticalAlignment="Center"/>
      </StackPanel>
    </Border>
    <Grid x:Name="chip" Grid.Column="1" Width="56" Height="56" RenderTransformOrigin="0.5,0.5" Focusable="True" Cursor="Hand"
          AutomationProperties.Name="Open BTP Assistant" ToolTip="BTP Assistant" Background="Transparent">
      <Grid.RenderTransform><ScaleTransform x:Name="chipScale" ScaleX="1" ScaleY="1"/></Grid.RenderTransform>
      <Ellipse x:Name="pulse" StrokeThickness="2" Opacity="0" RenderTransformOrigin="0.5,0.5" IsHitTestVisible="False">
        <Ellipse.RenderTransform><ScaleTransform x:Name="pulseScale" ScaleX="1" ScaleY="1"/></Ellipse.RenderTransform>
      </Ellipse>
      <Border x:Name="glow" CornerRadius="18"><Border.Effect><DropShadowEffect x:Name="glowFx" ShadowDepth="0" BlurRadius="22" Opacity="0.45"/></Border.Effect></Border>
      <Border x:Name="face" CornerRadius="18"><Border.Effect><DropShadowEffect ShadowDepth="3" BlurRadius="14" Opacity="0.45" Color="Black"/></Border.Effect></Border>
      <Border x:Name="hl" CornerRadius="18" BorderThickness="1" IsHitTestVisible="False"/>
      <TextBlock x:Name="logo" Text="BTP" FontFamily="Segoe UI" FontSize="15" FontWeight="Bold" HorizontalAlignment="Center"
                 VerticalAlignment="Center" TextOptions.TextFormattingMode="Display" IsHitTestVisible="False"/>
      <Border x:Name="focusRing" CornerRadius="21" BorderThickness="2" Margin="-4" Visibility="Collapsed" IsHitTestVisible="False"/>
      <Ellipse x:Name="dot" Width="13" Height="13" StrokeThickness="2" HorizontalAlignment="Right" VerticalAlignment="Bottom" Margin="0,0,-2,-2" IsHitTestVisible="False"/>
      <Ellipse x:Name="badge" Width="12" Height="12" StrokeThickness="2" HorizontalAlignment="Right" VerticalAlignment="Top" Margin="0,-2,-2,0" Visibility="Collapsed" IsHitTestVisible="False"/>
    </Grid>
  </Grid>
</Window>"""

    def _wc(self, c, a=255):
        from System.Windows.Media import Color as _WC
        return _WC.FromArgb(a, c.R, c.G, c.B)

    def _shade(self, c, f):
        if f >= 0:
            return Color.FromArgb(int(c.R + (255 - c.R) * f), int(c.G + (255 - c.G) * f), int(c.B + (255 - c.B) * f))
        f = -f
        return Color.FromArgb(int(c.R * (1 - f)), int(c.G * (1 - f)), int(c.B * (1 - f)))

    def _build_chip(self):
        import clr
        for a in ("PresentationFramework", "PresentationCore", "WindowsBase", "System.Xaml", "WindowsFormsIntegration"):
            try:
                clr.AddReference(a)
            except Exception:
                pass
        from System.Windows.Markup import XamlReader
        from System.Windows.Media import SolidColorBrush, LinearGradientBrush, GradientStop
        from System.Windows import Point as WP, SystemParameters, Thickness, Visibility
        from System.Windows.Interop import WindowInteropHelper
        win = XamlReader.Parse(self.CHIP_XAML)
        F = win.FindName
        acc = self.C_TEAL
        g = LinearGradientBrush()
        g.StartPoint = WP(0, 0)
        g.EndPoint = WP(1, 1)
        g.GradientStops.Add(GradientStop(self._wc(self._shade(acc, 0.22)), 0.0))
        g.GradientStops.Add(GradientStop(self._wc(self._shade(acc, -0.20)), 1.0))
        F("face").Background = g
        F("glow").Background = SolidColorBrush(self._wc(acc))
        F("glowFx").Color = self._wc(acc)
        hl = LinearGradientBrush()
        hl.StartPoint = WP(0.5, 0)
        hl.EndPoint = WP(0.5, 1)
        hl.GradientStops.Add(GradientStop(self._wc(Color.White, 110), 0.0))
        hl.GradientStops.Add(GradientStop(self._wc(Color.White, 0), 0.45))
        F("hl").BorderBrush = hl
        F("logo").Foreground = SolidColorBrush(self._wc(self.C_BG))
        ring = SolidColorBrush(self._wc(self.C_BG))
        F("dot").Stroke = ring
        F("badge").Stroke = ring
        F("badge").Fill = SolidColorBrush(self._wc(self._shade(acc, 0.35)))
        F("pulse").Stroke = SolidColorBrush(self._wc(acc))
        F("focusRing").BorderBrush = SolidColorBrush(self._wc(self.C_TEXT))
        pill = F("pill")
        pill.Background = SolidColorBrush(self._wc(self.C_CARD))
        pill.BorderBrush = SolidColorBrush(self._wc(self.C_LINE))
        pill.BorderThickness = Thickness(1)
        F("pillText").Foreground = SolidColorBrush(self._wc(self.C_TEXT))
        F("pillChev").Foreground = SolidColorBrush(self._wc(acc))
        WindowInteropHelper(win).Owner = __revit__.MainWindowHandle
        try:
            from System.Windows.Forms.Integration import ElementHost
            ElementHost.EnableModelessKeyboardInterop(win)
        except Exception:
            pass
        try:
            self._chip_motion = bool(SystemParameters.ClientAreaAnimation)
        except Exception:
            self._chip_motion = True
        chip = F("chip")
        chip.MouseEnter += lambda s, e: self._chip_hover(True)
        chip.MouseLeave += lambda s, e: self._chip_hover(False)
        chip.MouseLeftButtonDown += lambda s, e: self._chip_down(e)
        chip.MouseMove += lambda s, e: self._chip_move(e)
        chip.MouseLeftButtonUp += lambda s, e: self._chip_up(e)
        chip.KeyDown += lambda s, e: self._chip_key(e)
        chip.GotKeyboardFocus += lambda s, e: setattr(F("focusRing"), "Visibility", Visibility.Visible)
        chip.LostKeyboardFocus += lambda s, e: setattr(F("focusRing"), "Visibility", Visibility.Collapsed)
        try:
            win.DpiChanged += lambda s, e: self._chip_place(win.Top)
        except Exception:
            pass
        self._chipwin = win
        self._drag = None
        self._chip_set_status(getattr(self, "_chip_state", "online"))
        return win

    def _chip_anim(self, target, prop, to, ms, frm=None, repeat=None, done=None):
        from System.Windows.Media.Animation import DoubleAnimation, CubicEase, EasingMode, RepeatBehavior
        from System.Windows import Duration
        from System import TimeSpan
        if not getattr(self, "_chip_motion", True):
            target.BeginAnimation(prop, None)
            target.SetValue(prop, float(to))
            if done is not None:
                done()
            return
        da = DoubleAnimation()
        if frm is not None:
            da.From = float(frm)
        da.To = float(to)
        da.Duration = Duration(TimeSpan.FromMilliseconds(ms))
        ez = CubicEase()
        ez.EasingMode = EasingMode.EaseOut
        da.EasingFunction = ez
        if repeat:
            da.RepeatBehavior = RepeatBehavior(float(repeat))
        if done is not None:
            da.Completed += lambda s, e: done()
        target.BeginAnimation(prop, da)

    def _chip_scale(self, v, ms, done=None):
        from System.Windows.Media import ScaleTransform
        sc = self._chipwin.FindName("chipScale")
        self._chip_anim(sc, ScaleTransform.ScaleXProperty, v, ms)
        self._chip_anim(sc, ScaleTransform.ScaleYProperty, v, ms, done=done)

    def _chip_dpi(self):
        try:
            from System.Windows import PresentationSource
            src = PresentationSource.FromVisual(self._chipwin)
            if src is not None:
                return float(src.CompositionTarget.TransformToDevice.M22)
        except Exception:
            pass
        try:
            from System.Drawing import Graphics
            from System import IntPtr
            gr = Graphics.FromHwnd(IntPtr.Zero)
            d = gr.DpiY / 96.0
            gr.Dispose()
            return d
        except Exception:
            return 1.0

    def _chip_work(self):
        from System.Windows.Forms import Screen as _S
        wa = _S.FromHandle(__revit__.MainWindowHandle).WorkingArea
        d = self._chip_dpi()
        return wa.Left / d, wa.Top / d, wa.Right / d, wa.Bottom / d

    def _chip_path(self):
        return _os.path.join(self._rc_dir(), "chip.json")

    def _chip_load_y(self):
        try:
            import io as _io
            with _io.open(self._chip_path(), "r", encoding="utf-8-sig") as f:
                return float(json.load(f).get("y"))
        except Exception:
            return None

    def _chip_save_y(self, y):
        try:
            import io as _io
            with _io.open(self._chip_path(), "w", encoding="utf-8") as f:
                f.write(json.dumps({"y": float(y)}))
        except Exception:
            pass

    def _chip_place(self, y=None):
        win = self._chipwin
        l, tp, r, b = self._chip_work()
        if y is None:
            y = self._chip_load_y()
        if y is None:
            y = b - win.Height - 70
        win.Left = r - win.Width
        win.Top = max(tp, min(b - win.Height, y))

    def _chip_hover(self, on):
        from System.Windows.Media import ScaleTransform
        from System.Windows import UIElement
        if getattr(self, "_drag", None):
            return
        F = self._chipwin.FindName
        self._chip_scale(1.06 if on else 1.0, 170)
        self._chip_anim(F("pillScale"), ScaleTransform.ScaleXProperty, 1.0 if on else 0.0, 180)
        self._chip_anim(F("pill"), UIElement.OpacityProperty, 1.0 if on else 0.0, 180)

    def _chip_down(self, e):
        from System.Windows.Forms import Cursor as _Cur
        self._drag = {"y0": _Cur.Position.Y, "top0": self._chipwin.Top, "moved": False}
        self._chipwin.FindName("chip").CaptureMouse()
        self._chip_scale(0.96, 80)
        e.Handled = True

    def _chip_move(self, e):
        dg = getattr(self, "_drag", None)
        if not dg:
            return
        from System.Windows.Forms import Cursor as _Cur
        dy = (_Cur.Position.Y - dg["y0"]) / self._chip_dpi()
        if abs(dy) > 4:
            dg["moved"] = True
        if dg["moved"]:
            l, tp, r, b = self._chip_work()
            self._chipwin.Top = max(tp, min(b - self._chipwin.Height, dg["top0"] + dy))

    def _chip_up(self, e):
        dg = getattr(self, "_drag", None)
        self._drag = None
        try:
            self._chipwin.FindName("chip").ReleaseMouseCapture()
        except Exception:
            pass
        e.Handled = True
        if dg and dg["moved"]:
            self._chip_place(self._chipwin.Top)   # snap back to the right edge
            self._chip_save_y(self._chipwin.Top)
            self._chip_scale(1.06, 120)
        else:
            self._chip_scale(1.06, 80)
            self._restore_from_chip()

    def _chip_key(self, e):
        from System.Windows.Input import Key
        if e.Key in (Key.Enter, Key.Space):
            e.Handled = True
            self._restore_from_chip()

    def _chip_set_status(self, state):
        self._chip_state = state
        win = getattr(self, "_chipwin", None)
        if win is None:
            return
        from System.Windows.Media import SolidColorBrush
        col = {"online": Color.FromArgb(34, 197, 94), "busy": Color.FromArgb(245, 158, 11), "offline": Color.FromArgb(239, 68, 68)}.get(state, Color.FromArgb(34, 197, 94))
        win.FindName("dot").Fill = SolidColorBrush(self._wc(col))

    def _chip_notify(self):
        win = getattr(self, "_chipwin", None)
        if win is None or not win.IsVisible:
            return
        from System.Windows import Visibility, UIElement
        from System.Windows.Media import ScaleTransform
        F = win.FindName
        F("badge").Visibility = Visibility.Visible
        if getattr(self, "_chip_motion", True):
            ps = F("pulseScale")
            self._chip_anim(ps, ScaleTransform.ScaleXProperty, 1.35, 1600, frm=1.0, repeat=3)
            self._chip_anim(ps, ScaleTransform.ScaleYProperty, 1.35, 1600, frm=1.0, repeat=3)
            self._chip_anim(F("pulse"), UIElement.OpacityProperty, 0.0, 1600, frm=0.7, repeat=3)

    def _chip_clear_notify(self):
        win = getattr(self, "_chipwin", None)
        if win is None:
            return
        from System.Windows import Visibility, UIElement
        F = win.FindName
        F("badge").Visibility = Visibility.Collapsed
        F("pulse").BeginAnimation(UIElement.OpacityProperty, None)
        F("pulse").Opacity = 0.0

    def _chip_health_check(self):
        import threading
        win = self._chipwin
        url = BRAIN_URL.rstrip("/") + "/docs"
        def work():
            ok = False
            try:
                try:
                    import urllib.request as _u
                    _u.urlopen(url, timeout=3).read(64)
                except ImportError:
                    import urllib2 as _u2
                    _u2.urlopen(url, timeout=3).read(64)
                ok = True
            except Exception:
                ok = False
            try:
                from System import Action
                st = "online" if ok else "offline"
                win.Dispatcher.BeginInvoke(Action(lambda: None if getattr(self, "_chip_state", "") == "busy" else self._chip_set_status(st)))
            except Exception:
                pass
        th = threading.Thread(target=work)
        th.daemon = True
        th.start()

    def _collapse_to_chip(self):
        from System.Windows import UIElement
        self._save_bounds()
        try:
            if getattr(self, "_chipwin", None) is None:
                self._build_chip()
            win = self._chipwin
            F = win.FindName
            F("chip").BeginAnimation(UIElement.OpacityProperty, None)
            F("chip").Opacity = 1.0
            self._chip_scale(1.0, 1)
            self._panel_opacity = self.Opacity
            win.Left = -20000
            win.Top = -20000
            self.Hide()
            win.Show()
            self._chip_place()
            self._chip_health_check()
        except Exception as ex:
            self.Show()   # never lose the panel
            try:
                self.status_label.Text = "Could not minimise (%s)" % ex
            except Exception:
                pass

    def _restore_from_chip(self):
        from System.Windows.Forms import FormWindowState
        from System.Windows import UIElement
        win = getattr(self, "_chipwin", None)
        motion = getattr(self, "_chip_motion", True)
        def finish():
            try:
                win.Hide()
            except Exception:
                pass
            self._chip_clear_notify()
            target = getattr(self, "_panel_opacity", 1.0) or 1.0
            self.Opacity = 0.05 if motion else target
            self.Show()
            self.WindowState = FormWindowState.Normal
            self.Activate()
            if motion:
                self._fade_in(target)
        if win is not None and win.IsVisible and motion:
            self._chip_anim(win.FindName("chip"), UIElement.OpacityProperty, 0.0, 140)
            self._chip_scale(0.85, 140, done=finish)
        else:
            finish()

    def _fade_in(self, target):
        from System.Windows.Forms import Timer
        tm = Timer()
        tm.Interval = 30
        n = [0]
        def tick(s, e):
            n[0] += 1
            self.Opacity = min(target, target * n[0] / 6.0)
            if n[0] >= 6:
                tm.Stop()
                tm.Dispose()
        tm.Tick += tick
        tm.Start()

    def _on_visible(self):
        if self.Visible:
            try:
                win = getattr(self, "_chipwin", None)
                if win is not None and win.IsVisible:
                    win.Hide()
                    self._chip_clear_notify()
            except Exception:
                pass

    def _on_close_extras(self):
        self._save_bounds()
        try:
            if getattr(self, "_chipwin", None) is not None:
                self._chipwin.Close()
        except Exception:
            pass
        self._loading_remove()

    # ---- loading bubble while waiting for a reply ----
    LD_PHRASES = [u"Thinking\u2026", u"Reading your model\u2026", u"Checking elements\u2026", u"Almost there\u2026"]

    def _loading_start(self):
        self._chip_set_status("busy")
        from System.Windows.Forms import Timer, Button, FlatStyle, Cursors, SystemInformation
        self._loading_remove()
        self._ld_cancelled = False
        bw = max(260, min(self.chat_panel.ClientSize.Width - 110, 420))
        b = Panel()
        b.BackColor = self.C_CARD
        b.Size = Size(bw, 64)
        b.Margin = Padding(0, 2, 0, 12)
        self._ld_dots = [self._lbl(b, u"\u25CF", 16 + i * 16, 8, 16, 22, Font("Segoe UI", 10.0), self.C_MUTED) for i in range(3)]
        self._ld_text = self._lbl(b, self.LD_PHRASES[0], 16, 34, bw - 110, 20, Font("Segoe UI", 9.0), self.C_MUTED)
        st = Button()
        st.Text = "Stop"
        st.Size = Size(64, 26)
        st.Location = Point(bw - 80, 19)
        st.FlatStyle = FlatStyle.Flat
        st.BackColor = self.C_CARD
        st.ForeColor = self.C_TEXT
        st.FlatAppearance.BorderColor = self.C_LINE
        st.Cursor = Cursors.Hand
        st.Click += lambda s, e: self._loading_stop()
        b.Controls.Add(st)
        self._ld_stop = st
        self.chat_panel.Controls.Add(b)
        self._round(b, 14)
        self._ld_box = b
        try:
            self.scroll_chat_to_bottom()
        except Exception:
            pass
        self._ld_ticks = 0
        try:
            self._ld_anim = bool(SystemInformation.UIEffectsEnabled)
        except Exception:
            self._ld_anim = True
        tm = Timer()
        tm.Interval = 400
        tm.Tick += lambda s, e: self._loading_tick()
        tm.Start()
        self._ld_timer = tm

    def _loading_tick(self):
        if getattr(self, "_ld_box", None) is None or getattr(self, "_ld_cancelled", False):
            return
        self._ld_ticks += 1
        if not self._ld_anim:
            return   # reduced motion: static "Thinking..."
        k = self._ld_ticks % 3
        for i, d in enumerate(self._ld_dots):
            d.ForeColor = self.C_TEAL if i == k else self.C_MUTED
        secs = self._ld_ticks * 0.4
        if secs >= 10:
            self._ld_text.Text = u"Still working on it, this one's a bit big\u2026"
        else:
            self._ld_text.Text = self.LD_PHRASES[int(secs // 2.5) % len(self.LD_PHRASES)]

    def _loading_stop(self):
        self._ld_cancelled = True
        try:
            for d in self._ld_dots:
                d.Visible = False
            self._ld_text.Text = u"Stopping\u2026 the reply will be ignored when it arrives."
            self._ld_stop.Enabled = False
        except Exception:
            pass

    def _loading_remove(self):
        try:
            if getattr(self, "_ld_timer", None) is not None:
                self._ld_timer.Stop()
                self._ld_timer.Dispose()
        except Exception:
            pass
        self._ld_timer = None
        b = getattr(self, "_ld_box", None)
        self._ld_box = None
        if b is not None:
            try:
                self.chat_panel.Controls.Remove(b)
                b.Dispose()
            except Exception:
                pass

    def _check_with_loading(self, orig, sender, args):
        if not shared.get("finished"):
            return orig(sender, args)
        if getattr(self, "_ld_cancelled", False):
            try:
                self.check_timer.Stop()
            except Exception:
                pass
            shared["proposals"] = []
            shared["selection"] = None
            shared["answer"] = None
            self._ld_cancelled = False
            self._loading_remove()
            for c in (self.question_box, self.send_button, self.attach_button):
                c.Enabled = True
            self.status_label.Text = "Stopped. The late reply was ignored."
            self._chip_set_status("online")
            return
        ans = u"%s" % (shared.get("answer") or "")
        failed = ("[Connection error]" in ans) or ("[Error] HTTP" in ans)
        if failed:
            detail = ans.replace("BTP Assistant: ", "")[:140]
            shared["answer"] = u"BTP Assistant: Sorry, I couldn't get a reply this time - the assistant may be offline, busy or slow. Nothing was changed in your model. (%s)" % detail
        self._loading_remove()
        orig(sender, args)
        self._chip_set_status("offline" if failed else "online")
        if not self.Visible:
            self._chip_notify()
        if failed:
            self._retry_chip(getattr(self, "_last_question", u""))

    def _retry_chip(self, q):
        from System.Windows.Forms import Button, FlatStyle, Cursors
        if not q:
            return
        b = Panel()
        b.BackColor = self.C_BG
        b.Size = Size(200, 40)
        b.Margin = Padding(0, 0, 0, 12)
        bt = Button()
        bt.Text = "Retry"
        bt.Location = Point(0, 4)
        bt.Size = Size(90, 30)
        bt.FlatStyle = FlatStyle.Flat
        bt.BackColor = self.C_TEAL
        bt.ForeColor = self.C_BG
        bt.FlatAppearance.BorderSize = 0
        bt.Cursor = Cursors.Hand
        def go(s, e):
            if self._busy():
                return
            try:
                self.chat_panel.Controls.Remove(b)
                b.Dispose()
            except Exception:
                pass
            self.question_box.Text = q
            self.send_question(None, None)   # the same send path as the input box
        bt.Click += go
        b.Controls.Add(bt)
        self.chat_panel.Controls.Add(b)
        try:
            self.scroll_chat_to_bottom()
        except Exception:
            pass

    def _theme_layout_safe(self):
        try:
            self._theme_layout()
        except Exception:
            pass

    def _theme_layout(self):
        cw, ch = self.ClientSize.Width, self.ClientSize.Height
        S, HH, IH, SH = 64, 70, 64, 22
        w = cw - S
        self._sb.Location = Point(0, 0)
        self._sb.Size = Size(S, ch)
        self.header.Location = Point(S, 0)
        self.header.Size = Size(w, HH)
        self._h_set.Left = w - 116
        self._h_min.Left = w - 82
        self._h_cls.Left = w - 46
        self._h_new.Left = w - 212
        self.chat_panel.Location = Point(S, HH)
        self.chat_panel.Size = Size(w, ch - HH - IH - SH - 20)
        self.input_panel.Location = Point(S + 12, ch - IH - SH - 10)
        self.input_panel.Size = Size(w - 24, IH)
        iw = w - 24
        self.attach_button.Location = Point(-400, 12)
        self.attach_button.Size = Size(40, 40)
        self.send_button.Location = Point(iw - 50, 12)
        self.send_button.Size = Size(40, 40)
        self.question_box.Location = Point(60, 20)
        self.question_box.Size = Size(iw - 120, 26)
        self._round(self.input_panel, 16)
        self._round(self._clip, 20)
        self._clip_note.Location = Point(S + 20, ch - IH - SH - 28)
        self._round(self.send_button, 20)
        self.status_label.Location = Point(S + 14, ch - SH - 4)
        self.status_label.Size = Size(w - 28, SH)
        for v in (self._hist_view, self._set_view):
            v.Location = Point(S, HH)
            v.Size = Size(w, ch - HH)
        self._layout_welcome(w)

    def _layout_welcome(self, w):
        from System.Drawing import ContentAlignment
        card = self._welcome
        cw = w - 32 - 24
        for c in list(card.Controls):
            card.Controls.Remove(c)
        card.Width = cw
        card.Margin = Padding(0, 4, 0, 14)
        self._lbl(card, u"\uE8BD", 18, 18, 40, 40, Font("Segoe MDL2 Assets", 16.0), self.C_TEAL, ContentAlignment.MiddleCenter)
        self._lbl(card, "Hello Sindhu", 66, 16, cw - 80, 26, Font("Segoe UI", 12.0, Enum.ToObject(FontStyle, 1)), self.C_TEXT)
        self._lbl(card, "I'm your BTP Revit Agent. I can help you query your model, find issues, and perform actions directly in Revit.", 66, 44, cw - 84, 40, Font("Segoe UI", 9.0), self.C_MUTED, ContentAlignment.TopLeft)
        tiles = [(u"\uE721", "Query Model", "How many doors are on L1?"),
                 (u"\uEA18", "Run Audit", "Run a model health report."),
                 (u"\uE8B3", "Select Elements", "Select all doors on L1."),
                 (u"\uE9E9", "Set Parameter", "Set Comments to 'checked' on all doors on L1."),
                 (u"\uE710", "Create / Modify", "Create a wall on L1 from (0, 0) to (5, 0)."),
                 (u"\uE712", "More Actions", "What else can you do?")]
        gap, cols = 10, 3
        tw = (cw - 36 - gap * (cols - 1)) // cols
        for i, (g, name, pr) in enumerate(tiles):
            r, c = divmod(i, cols)
            self._tile(card, g, name, 18 + c * (tw + gap), 94 + r * 46, tw, 38, pr)
        card.Height = 94 + 2 * 46 + 12
        self._round(card, 14)

    def question_box_key_down(
        self,
        sender,
        args
    ):

        if args.KeyCode == Keys.Enter:

            args.SuppressKeyPress = True

            self.send_question(
                None,
                None
            )


    # ========================================================
    # KEYBOARD HOOK INSTALL
    # ========================================================

    def _install_keyboard_hook(self):

        try:

            ctypes.set_last_error(0)

            self._keyboard_hook_id = (
                user32.SetWindowsHookExW(
                    WH_KEYBOARD_LL,
                    self._keyboard_hook_proc,
                    None,
                    0
                )
            )

            if not self._keyboard_hook_id:

                err_code = ctypes.get_last_error()

                self.status_label.Text = (
                    "Keyboard hook failed: "
                    + str(err_code)
                )

        except Exception as e:

            self.status_label.Text = (
                "Keyboard hook error: "
                + str(e)
            )


    # ========================================================
    # KEYBOARD HOOK CALLBACK
    # ========================================================

    def _low_level_keyboard_callback(
        self,
        nCode,
        wParam,
        lParam
    ):

        try:

            if (
                nCode == 0
                and wParam == WM_KEYDOWN
            ):

                kb = ctypes.cast(
                    lParam,
                    ctypes.POINTER(
                        KBDLLHOOKSTRUCT
                    )
                ).contents

                if kb.vkCode == VK_V:

                    ctrl_down = (
                        user32.GetAsyncKeyState(
                            VK_CONTROL
                        )
                        & 0x8000
                    ) != 0

                    if (
                        ctrl_down
                        and self.question_box.Focused
                    ):

                        image_pasted = (
                            self.try_paste_image_from_clipboard()
                        )

                        if image_pasted:

                            return 1

        except Exception:

            pass

        return user32.CallNextHookEx(
            self._keyboard_hook_id,
            nCode,
            wParam,
            lParam
        )


    # ========================================================
    # FORM CLOSING
    # ========================================================

    def _on_form_closing(
        self,
        sender,
        args
    ):

        if self._keyboard_hook_id:

            user32.UnhookWindowsHookEx(
                self._keyboard_hook_id
            )

            self._keyboard_hook_id = None


    # ========================================================
    # SCROLL CHAT TO BOTTOM
    # ========================================================

    def scroll_chat_to_bottom(self):

        try:

            self.chat_panel.VerticalScroll.Value = (
                self.chat_panel.VerticalScroll.Maximum
            )

            self.chat_panel.PerformLayout()

        except Exception:

            pass


    # ========================================================
    # CREATE MESSAGE CONTAINER
    # ========================================================

    def create_message_container(self):

        container = Panel()

        container.Width = 420

        container.AutoSize = True

        from System.Windows.Forms import AutoSizeMode
        from System.Windows.Forms import Padding

        container.AutoSizeMode = Enum.ToObject(
            AutoSizeMode,
            1
        )

        container.Margin = Padding(
            5,
            5,
            5,
            5
        )

        return container


    # ========================================================
    # DISPLAY USER MESSAGE
    #
    # USER = RIGHT
    # IMAGE(S) = RIGHT
    # ========================================================

    def append_user_message(
        self,
        text,
        image_base64_list
    ):

        container = Panel()

        container.Width = 498

        container.AutoSize = True

        container.AutoSizeMode = Enum.ToObject(
            AutoSizeMode,
            1
        )

        container.Margin = Padding(
            0,
            4,
            0,
            14
        )

        container.BackColor = Color.FromArgb(
            241,
            245,
            249
        )

        current_y = 0

        # ----------------------------------------------------
        # USER LABEL
        # ----------------------------------------------------

        user_label = Label()

        user_label.Text = "You"

        user_label.AutoSize = True

        user_label.Font = Font(
            "Segoe UI Semibold",
            8,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        user_label.ForeColor = Color.FromArgb(
            100,
            116,
            139
        )

        container.Controls.Add(
            user_label
        )

        user_label.Location = Point(
            container.Width
            - user_label.Width
            - 8,
            current_y
        )

        current_y += 22

        # ----------------------------------------------------
        # MULTIPLE IMAGES
        # ----------------------------------------------------

        if image_base64_list:

            for image_base64 in image_base64_list:

                if not image_base64:
                    continue

                try:

                    raw_bytes = base64.b64decode(
                        image_base64
                    )

                    stream = MemoryStream(
                        raw_bytes
                    )

                    source_image = Bitmap.FromStream(
                        stream
                    )

                    display_image = Bitmap(
                        source_image
                    )

                    source_image.Dispose()
                    stream.Dispose()

                    max_width = 365
                    max_height = 210

                    original_width = (
                        display_image.Width
                    )

                    original_height = (
                        display_image.Height
                    )

                    if (
                        original_width > 0
                        and original_height > 0
                    ):

                        ratio = (
                            float(original_height)
                            / float(original_width)
                        )

                        image_width = min(
                            original_width,
                            max_width
                        )

                        image_height = int(
                            image_width * ratio
                        )

                        if image_height > max_height:

                            image_height = max_height

                            image_width = int(
                                image_height / ratio
                            )

                    else:

                        image_width = 320
                        image_height = 180

                    image_frame = Panel()

                    image_frame.Size = Size(
                        image_width + 8,
                        image_height + 8
                    )

                    image_frame.Location = Point(
                        container.Width
                        - image_frame.Width
                        - 8,
                        current_y
                    )

                    image_frame.BackColor = Color.FromArgb(
                        226,
                        232,
                        240
                    )

                    image_frame.BorderStyle = Enum.ToObject(
                        BorderStyle,
                        1
                    )

                    picture = PictureBox()

                    picture.SizeMode = Enum.ToObject(
                        PictureBoxSizeMode,
                        4
                    )

                    picture.Image = display_image

                    picture.Location = Point(
                        4,
                        4
                    )

                    picture.Size = Size(
                        image_width,
                        image_height
                    )

                    image_frame.Controls.Add(
                        picture
                    )

                    container.Controls.Add(
                        image_frame
                    )

                    current_y += (
                        image_frame.Height
                        + 8
                    )

                except Exception as e:

                    error_label = Label()

                    error_label.Text = (
                        "[Image display error] "
                        + str(e)
                    )

                    error_label.AutoSize = True

                    error_label.ForeColor = Color.Red

                    error_label.Location = Point(
                        100,
                        current_y
                    )

                    container.Controls.Add(
                        error_label
                    )

                    current_y += (
                        error_label.Height
                        + 8
                    )

        # ----------------------------------------------------
        # USER MESSAGE BUBBLE
        # ----------------------------------------------------

        bubble = Panel()

        bubble.AutoSize = True

        bubble.AutoSizeMode = Enum.ToObject(
            AutoSizeMode,
            1
        )

        bubble.MaximumSize = Size(
            370,
            0
        )

        bubble.BackColor = Color.FromArgb(
            52,
            120,
            185
        )

        message_label = Label()

        message_label.Text = text

        message_label.AutoSize = True

        message_label.MaximumSize = Size(
            346,
            0
        )

        message_label.Padding = Padding(
            12,
            8,
            12,
            8
        )

        message_label.Font = Font(
            "Segoe UI",
            9.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        message_label.ForeColor = Color.White

        message_label.BackColor = Color.Transparent

        bubble.Controls.Add(
            message_label
        )

        bubble.Width = min(
            message_label.Width,
            370
        )

        bubble.Height = message_label.Height

        bubble.Location = Point(
            container.Width
            - bubble.Width
            - 8,
            current_y
        )

        container.Controls.Add(
            bubble
        )

        current_y += (
            bubble.Height
            + 5
        )

        container.Height = (
            current_y
            + 5
        )

        self.chat_panel.Controls.Add(
            container
        )

        self.scroll_chat_to_bottom()


    # ========================================================
    # DISPLAY ASSISTANT MESSAGE
    #
    # ASSISTANT = LEFT
    # ========================================================

    def append_assistant_message(
        self,
        text
    ):

        container = Panel()

        container.Width = 498

        container.AutoSize = True

        container.AutoSizeMode = Enum.ToObject(
            AutoSizeMode,
            1
        )

        container.Margin = Padding(
            0,
            4,
            0,
            12
        )

        container.BackColor = Color.FromArgb(
            251,
            252,
            254
        )

        container.BorderStyle = Enum.ToObject(
            BorderStyle,
            0
        )

        # ----------------------------------------------------
        # ASSISTANT HEADER
        # ----------------------------------------------------

        badge = Label()

        badge.Text = "BTP"

        badge.TextAlign = Enum.ToObject(
            ContentAlignment,
            32
        )

        badge.Location = Point(
            14,
            12
        )

        badge.Size = Size(
            34,
            26
        )

        badge.BackColor = Color.FromArgb(
            37,
            99,
            168
        )

        badge.ForeColor = Color.White

        badge.Font = Font(
            "Segoe UI",
            7.5,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        container.Controls.Add(
            badge
        )

        name_label = Label()

        name_label.Text = "BTP Assistant"

        name_label.Location = Point(
            58,
            10
        )

        name_label.Size = Size(
            160,
            20
        )

        name_label.ForeColor = Color.FromArgb(
            23,
            32,
            51
        )

        name_label.Font = Font(
            "Segoe UI Semibold",
            9,
            Enum.ToObject(
                FontStyle,
                1
            )
        )

        container.Controls.Add(
            name_label
        )

        sub_label = Label()

        sub_label.Text = "BIM model assistant"

        sub_label.Location = Point(
            58,
            29
        )

        sub_label.Size = Size(
            180,
            17
        )

        sub_label.ForeColor = Color.FromArgb(
            100,
            116,
            139
        )

        sub_label.Font = Font(
            "Segoe UI",
            7.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        container.Controls.Add(
            sub_label
        )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        answer_label = Label()

        answer_label.Text = text

        answer_label.AutoSize = True

        answer_label.MaximumSize = Size(
            462,
            0
        )

        answer_label.Padding = Padding(
            12,
            8,
            12,
            12
        )

        answer_label.Font = Font(
            "Segoe UI",
            9.5,
            Enum.ToObject(
                FontStyle,
                0
            )
        )

        answer_label.ForeColor = Color.FromArgb(
            51,
            65,
            85
        )

        answer_label.Location = Point(
            4,
            52
        )

        container.Controls.Add(
            answer_label
        )

        container.Height = (
            answer_label.Location.Y
            + answer_label.Height
            + 8
        )

        self.chat_panel.Controls.Add(
            container
        )

        self.scroll_chat_to_bottom()


    # ========================================================
    # ATTACH IMAGE - FILE PICKER
    # ========================================================

    def attach_image(
        self,
        sender,
        args
    ):

        dialog = OpenFileDialog()

        dialog.Title = "Select BIM Image(s)"

        dialog.Filter = (
            "Image files (*.png;*.jpg;*.jpeg)|"
            "*.png;*.jpg;*.jpeg"
        )

        dialog.Multiselect = True

        dialog.ShowDialog()

        filenames = dialog.FileNames

        if filenames is None:
            return

        try:

            added_count = 0

            for filename in filenames:

                if not filename:
                    continue

                # --------------------------------------------
                # Convert every selected image to PNG.
                # This keeps the backend data URL correct.
                # --------------------------------------------

                bitmap = Bitmap(filename)

                stream = MemoryStream()

                bitmap.Save(
                    stream,
                    ImageFormat.Png
                )

                raw_bytes = stream.ToArray()

                bitmap.Dispose()
                stream.Dispose()

                image_base64 = (
                    base64.b64encode(
                        bytes(raw_bytes)
                    ).decode("utf-8")
                )

                self.pending_images.append(
                    image_base64
                )

                added_count += 1

            if added_count == 0:
                return

            total_count = len(
                self.pending_images
            )

            if total_count == 1:

                self.attach_button.Text = (
                    "1 Image Attached"
                )

            else:

                self.attach_button.Text = (
                    str(total_count)
                    + " Images Attached"
                )

            self.status_label.Text = (
                str(total_count)
                + " image(s) ready"
            )

            self.question_box.Focus()

        except Exception as e:

            self.status_label.Text = (
                "Image error: "
                + str(e)
            )


    # ========================================================
    # ATTACH IMAGE - CLIPBOARD
    # ========================================================

    def try_paste_image_from_clipboard(
        self
    ):

        # ----------------------------------------------------
        # CASE 1: ACTUAL IMAGE DATA
        # ----------------------------------------------------

        if Clipboard.ContainsImage():

            try:

                image = Clipboard.GetImage()

                stream = MemoryStream()

                image.Save(
                    stream,
                    ImageFormat.Png
                )

                raw_bytes = (
                    stream.ToArray()
                )

                stream.Dispose()

                image_base64 = (
                    base64.b64encode(
                        bytes(raw_bytes)
                    ).decode("utf-8")
                )

                self.pending_images.append(
                    image_base64
                )

                total_count = len(
                    self.pending_images
                )

                if total_count == 1:

                    self.attach_button.Text = (
                        "1 Image Attached"
                    )

                else:

                    self.attach_button.Text = (
                        str(total_count)
                        + " Images Attached"
                    )

                self.status_label.Text = (
                    str(total_count)
                    + " image(s) ready"
                )

                self.question_box.Focus()

                return True

            except Exception as e:

                self.status_label.Text = (
                    "Paste error: "
                    + str(e)
                )

                return False

        # ----------------------------------------------------
        # CASE 2: COPIED IMAGE FILE
        # ----------------------------------------------------

        if Clipboard.ContainsFileDropList():

            try:

                file_list = (
                    Clipboard.GetFileDropList()
                )

                if file_list.Count == 0:

                    return False

                added_count = 0

                for i in range(
                    file_list.Count
                ):

                    filename = file_list[i]

                    lower_name = filename.lower()

                    if not (
                        lower_name.endswith(".png")
                        or lower_name.endswith(".jpg")
                        or lower_name.endswith(".jpeg")
                    ):

                        continue

                    bitmap = Bitmap(filename)

                    stream = MemoryStream()

                    bitmap.Save(
                        stream,
                        ImageFormat.Png
                    )

                    raw_bytes = stream.ToArray()

                    bitmap.Dispose()
                    stream.Dispose()

                    image_base64 = (
                        base64.b64encode(
                            bytes(raw_bytes)
                        ).decode("utf-8")
                    )

                    self.pending_images.append(
                        image_base64
                    )

                    added_count += 1

                if added_count == 0:

                    return False

                total_count = len(
                    self.pending_images
                )

                if total_count == 1:

                    self.attach_button.Text = (
                        "1 Image Attached"
                    )

                else:

                    self.attach_button.Text = (
                        str(total_count)
                        + " Images Attached"
                    )

                self.status_label.Text = (
                    str(total_count)
                    + " image(s) ready"
                )

                self.question_box.Focus()

                return True

            except Exception as e:

                self.status_label.Text = (
                    "Paste error: "
                    + str(e)
                )

                return False

        # ----------------------------------------------------
        # NORMAL TEXT CLIPBOARD
        # ----------------------------------------------------

        return False


    # ========================================================
    # SEND QUESTION
    # ========================================================

    def send_question(
        self,
        sender,
        args
    ):

        text = self.question_box.Text

        if text is None:

            return

        text = str(text).strip()

        if not text:

            self.status_label.Text = (
                "Please enter a question."
            )

            return

        self.question = text

        self.submitted = True

        # ----------------------------------------------------
        # CAPTURE ALL IMAGES FOR THIS TURN
        # ----------------------------------------------------

        images_for_this_turn = list(
            self.pending_images
        )

        # ----------------------------------------------------
        # DISPLAY USER MESSAGE
        # ----------------------------------------------------

        self.append_user_message(
            text,
            images_for_this_turn
        )

        # ----------------------------------------------------
        # CLEAR CURRENT IMAGES
        # ----------------------------------------------------

        self.pending_images = []

        self.attach_button.Text = (
            "Attach Image"
        )

        # ----------------------------------------------------
        # CLEAR QUESTION BOX
        # ----------------------------------------------------

        self.question_box.Text = ""

        self.question_box.Enabled = False

        self.send_button.Enabled = False

        self.attach_button.Enabled = False

        self.status_label.Text = "Thinking..."

        shared["finished"] = False

        shared["answer"] = None
        shared["proposals"] = []

        # ----------------------------------------------------
        # START BACKGROUND REQUEST
        # ----------------------------------------------------

        worker = threading.Thread(
            target=self.send_request,
            args=(images_for_this_turn,)
        )

        worker.daemon = True

        worker.start()

        self.check_timer = (
            self.create_timer()
        )

        self.check_timer.Start()


    # ========================================================
    # CREATE TIMER
    # ========================================================

    def create_timer(self):

        from System.Windows.Forms import Timer

        timer = Timer()

        timer.Interval = 200

        timer.Tick += self.check_response

        return timer


    # ========================================================
    # SEND HTTP REQUEST
    # ========================================================

    def send_request(
        self,
        image_payload
    ):

        payload = {
            "session_id":
                BRAIN_SESSION_ID,

            "user_message":
                self.question,

            "image_base64":
                image_payload
        }

        data = json.dumps(
            payload
        ).encode("utf-8")

        request = urllib.request.Request(
            "http://127.0.0.1:8000/chat",
            data=data,
            headers={
                "Content-Type":
                    "application/json"
            }
        )

        try:

            response = (
                urllib.request.urlopen(
                    request,
                    timeout=120
                )
            )

            response_bytes = (
                response.read()
            )

            result = json.loads(
                response_bytes.decode(
                    "utf-8"
                )
            )

            shared["proposals"] = result.get("proposals") or []
            shared["selection"] = result.get("selection")
            answer = result.get(
                "response",
                "No response received."
            )

            shared["answer"] = (
                "BTP Assistant: "
                + str(answer)
            )

        except urllib.error.HTTPError as e:

            try:

                error_body = (
                    e.read().decode(
                        "utf-8"
                    )
                )

            except Exception:

                error_body = str(e)

            shared["answer"] = (
                "BTP Assistant: "
                "[Error] HTTP "
                + str(e.code)
                + " - "
                + error_body
            )

        except Exception as e:

            shared["answer"] = (
                "BTP Assistant: "
                "[Connection error] "
                + str(e)
            )

        finally:

            shared["finished"] = True


    # ========================================================
    # CHECK RESPONSE
    # ========================================================

    def check_response(
        self,
        sender,
        args
    ):

        if not shared["finished"]:

            return

        self.check_timer.Stop()

        answer = shared["answer"]

        if answer is None:

            answer = (
                "BTP Assistant: "
                "No response received."
            )

        # ----------------------------------------------------
        # DISPLAY ASSISTANT RESPONSE
        # ----------------------------------------------------

        self.append_assistant_message(
            answer
        )

        try:   # Action Preview card when this reply selected elements
            _sel = shared.pop("selection", None)
            if _sel and _sel.get("count"):
                self._selection_card(_sel)
        except Exception:
            pass

        self.status_label.Text = ""

        # ----------------------------------------------------
        # ENABLE INPUT AGAIN
        # ----------------------------------------------------

        self.question_box.Enabled = True

        self.send_button.Enabled = True

        self.attach_button.Enabled = True

        self.question_box.Focus()


# ============================================================
# START CHAT
# ============================================================

# ============================================================
# PHASE 5 (step 4): PROPOSAL CARDS + CONFIRM / REJECT
# A change can be applied ONLY through fix_handler (ExternalEvent),
# and only after a Confirm click on a card.
# ============================================================

import os as _os
import sys as _sys
import traceback as _tb

_LIB = r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\lib"
if _LIB not in _sys.path:
    _sys.path.append(_LIB)

BRAIN_URL = "http://127.0.0.1:8000"
BRAIN_SESSION_ID = "revit_btp_session"
FAKE_PROPOSAL_FILE = r"C:\Users\sindh\OneDrive\Desktop\BTP\BIM_AGENT\logs\fake_proposal.json"

_PANEL = {
    "proposals": {}, "cards": {}, "timer": None, "inbox": [],
    "handler": None, "event": None, "error": None, "current": None
}
_LOCK = threading.Lock()

def _post_json(path, body):
    data = json.dumps(body, default=str).encode("utf-8")
    req = urllib.request.Request(
        BRAIN_URL + path, data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _report_worker(kind, pid, result):
    # background thread: talks to the brain, never touches the UI
    try:
        if kind == "result":
            reply = _post_json(
                "/proposals/%s/result" % pid,
                {"session_id": BRAIN_SESSION_ID, "result": result}
            )
        else:
            reply = _post_json(
                "/proposals/%s/reject" % pid,
                {"session_id": BRAIN_SESSION_ID}
            )
        text = str(reply.get("text", "Done."))
    except Exception as ex:
        text = "[Report error] " + str(ex)
    with _LOCK:
        _PANEL["inbox"].append({"pid": pid, "kind": kind, "text": text})


def _on_fix_done(result):
    # runs on Revit's thread right after the Transaction: only start a thread
    try:
        _fix_handler.log("panel: apply finished, status=" + str(result.get("status")))
    except Exception:
        pass
    t = threading.Thread(
        target=_report_worker,
        args=("result", _PANEL["current"], result)
    )
    t.daemon = True
    t.start()


try:
    import fix_handler as _fix_handler
    _h, _e = _fix_handler.create_apply_event(_on_fix_done)
    _PANEL["handler"] = _h
    _PANEL["event"] = _e
except Exception:
    _PANEL["error"] = _tb.format_exc()


# The Revit API import above can shadow WinForms/Drawing names (e.g. Color).
# Re-bind the names this panel uses to the System.* versions.
from System.Drawing import (
    Point, Size, Color, Font, FontStyle, Bitmap, Rectangle, ContentAlignment
)
from System.Windows.Forms import (
    Form, Label, TextBox, Button, Panel, FlowLayoutPanel, PictureBox,
    Padding, BorderStyle, FlatStyle, Keys
)


def _append_proposal_card(self, p):
    pid = p["proposal_id"]
    p["_state"] = "pending"
    _PANEL["proposals"][pid] = p
    args = p["args"]
    items = p.get("items") or []

    container = Panel()
    container.Width = 498
    container.Margin = Padding(0, 4, 0, 12)
    container.BackColor = Color.FromArgb(255, 248, 225)

    pos = [8]

    def add_label(text, bold=False, color=None, height=20):
        lbl = Label()
        lbl.Text = text
        lbl.AutoSize = False
        lbl.Location = Point(12, pos[0])
        lbl.Size = Size(472, height)
        lbl.Font = Font("Segoe UI", 9.0, Enum.ToObject(FontStyle, 1 if bold else 0))
        lbl.ForeColor = color if color is not None else Color.FromArgb(51, 65, 85)
        container.Controls.Add(lbl)
        pos[0] += height
        return lbl

    add_label("PROPOSED CHANGE  (%s)" % pid, bold=True)
    if p.get("function") == "run_action":
        add_label("Action: %s" % args.get("description", ""), height=36)
    else:
        add_label("Set '%s' = '%s' on %s" % (args["param_name"], args["value"], args["category"]))
    def _line(it):
        return ("- id %s %s [%s] %s:  '%s'  ->  '%s'" % (it.get("target_id"), it.get("label"), it.get("scope"), it.get("param_name"), it.get("old"), it.get("new")) if it.get("param_name") else "- %s [%s]:  '%s'  ->  '%s'" % (it.get("label"), it.get("scope"), it.get("old"), it.get("new")))
    if len(items) <= 30:
        for it in items:
            add_label(_line(it), height=36)
    else:   # big card: grouped summary + first 10 items; the full list is kept and re-checked on Confirm
        groups, order = {}, []
        for it in items:
            k = (str(it.get("label")), str(it.get("scope")), str(it.get("param_name") or ""), str(it.get("new"))[:60])
            if k not in groups:
                groups[k] = 0
                order.append(k)
            groups[k] += 1
        add_label("Summary of %d changes, grouped:" % len(items), bold=True)
        for k in sorted(order, key=lambda x: -groups[x])[:15]:
            add_label("- %d x %s [%s]%s -> '%s'" % (groups[k], k[0], k[1], (" " + k[2]) if k[2] else "", k[3]), height=36)
        if len(order) > 15:
            add_label("- ... %d more groups" % (len(order) - 15))
        add_label("First 10 of %d:" % len(items), bold=True)
        for it in items[:10]:
            add_label(_line(it), height=36)
        add_label("... and %d more (all are checked again on Confirm)" % (len(items) - 10))
    type_total = 0
    has_type = False
    for it in items:
        if it.get("scope") == "type":
            has_type = True
            type_total += int(it.get("affected", 1))
    if has_type:
        add_label(
            "TYPE-level change: affects %d elements in total" % type_total,
            bold=True, color=Color.FromArgb(185, 28, 28), height=22
        )
    n_del = len([it for it in items if str(it.get("scope", "")).startswith("deleted")])
    if n_del:
        add_label("DELETES %d element%s. Undo with Ctrl+Z after applying." % (n_del, "" if n_del == 1 else "s"),
                  bold=True, color=Color.FromArgb(185, 28, 28), height=22)
    add_label("Nothing is applied until you click Confirm.", height=20)

    confirm = Button()
    confirm.Text = "Confirm"
    confirm.Location = Point(12, pos[0] + 4)
    confirm.Size = Size(110, 30)
    reject = Button()
    reject.Text = "Reject"
    reject.Location = Point(130, pos[0] + 4)
    reject.Size = Size(110, 30)
    status = Label()
    status.Text = ""
    status.AutoSize = False
    status.Location = Point(250, pos[0] + 9)
    status.Size = Size(230, 22)
    container.Controls.Add(confirm)
    container.Controls.Add(reject)
    container.Controls.Add(status)
    container.Height = pos[0] + 4 + 30 + 10

    def make_confirm(x):
        return lambda s, e: self._on_confirm(x)

    def make_reject(x):
        return lambda s, e: self._on_reject(x)

    confirm.Click += make_confirm(pid)
    reject.Click += make_reject(pid)
    _PANEL["cards"][pid] = {"confirm": confirm, "reject": reject, "status": status}

    self.chat_panel.Controls.Add(container)
    self.scroll_chat_to_bottom()


def _ensure_report_timer(self):
    if _PANEL["timer"] is not None:
        return
    from System.Windows.Forms import Timer
    t = Timer()
    t.Interval = 300
    t.Tick += self._on_report_tick
    t.Start()
    _PANEL["timer"] = t


def _on_report_tick(self, sender, args):
    with _LOCK:
        items = list(_PANEL["inbox"])
        _PANEL["inbox"].clear()
    for it in items:
        card = _PANEL["cards"].get(it["pid"])
        p = _PANEL["proposals"].get(it["pid"])
        if card is not None and p is not None:
            if it["kind"] == "reject":
                card["status"].Text = "Rejected"
            elif it["text"].startswith("Applied"):
                p["_state"] = "applied"
                card["status"].Text = "Applied"
            else:
                p["_state"] = "not applied"
                card["status"].Text = "Not applied"
        self.append_assistant_message("BTP Assistant: " + it["text"])


def _on_confirm(self, pid):
    card = _PANEL["cards"].get(pid)
    p = _PANEL["proposals"].get(pid)
    if card is None or p is None or p.get("_state") != "pending":
        return
    if _PANEL["event"] is None or _PANEL["handler"] is None:
        card["status"].Text = "Apply unavailable (see log)"
        return
    # C21: ask the brain first; only the newest pending card may be applied (refuse if the check fails)
    try:
        _st = _post_json("/proposals/%s/status" % pid, {"session_id": BRAIN_SESSION_ID}).get("status")
    except Exception as _ex:
        _st = "status check failed: " + str(_ex)
    if _st != "pending":
        p["_state"] = "superseded"
        card["confirm"].Enabled = False
        card["reject"].Enabled = False
        card["status"].Text = "Not applied"
        self.append_assistant_message("BTP Assistant: This card can no longer be applied (%s). Only the newest proposal can be confirmed; ask again if you still want this change." % _st)
        return
    p["_state"] = "applying"
    card["confirm"].Enabled = False
    card["reject"].Enabled = False
    card["status"].Text = "Applying..."
    _PANEL["current"] = pid
    _PANEL["handler"].request = {
        "function": p["function"],
        "args": p["args"],
        "expected_old": p["expected_old"]
    }
    _PANEL["event"].Raise()
    self._ensure_report_timer()


def _on_reject(self, pid):
    card = _PANEL["cards"].get(pid)
    p = _PANEL["proposals"].get(pid)
    if card is None or p is None or p.get("_state") != "pending":
        return
    p["_state"] = "rejected"
    card["confirm"].Enabled = False
    card["reject"].Enabled = False
    card["status"].Text = "Rejecting..."
    t = threading.Thread(target=_report_worker, args=("reject", pid, None))
    t.daemon = True
    t.start()
    self._ensure_report_timer()


ChatForm._append_proposal_card = _append_proposal_card
ChatForm._ensure_report_timer = _ensure_report_timer
ChatForm._on_report_tick = _on_report_tick
ChatForm._on_confirm = _on_confirm
ChatForm._on_reject = _on_reject

_orig_check_response = ChatForm.check_response


def _check_response_with_cards(self, sender, args):
    was_finished = shared["finished"]
    _orig_check_response(self, sender, args)
    if was_finished:
        props = shared.get("proposals") or []
        shared["proposals"] = []
        for p in props:
            try:
                self._append_proposal_card(p)
            except Exception as ex:
                self.append_assistant_message("BTP Assistant: [Card error] " + str(ex))


ChatForm.check_response = _check_response_with_cards


def _show_fake_proposal_if_any(form):
    # test hook: draws one card from logs\fake_proposal.json, then deletes the file
    try:
        if not _os.path.exists(FAKE_PROPOSAL_FILE):
            return
        with open(FAKE_PROPOSAL_FILE, "r", encoding="utf-8-sig") as f:
            p = json.load(f)
        _os.remove(FAKE_PROPOSAL_FILE)
        form._append_proposal_card(p)
    except Exception as ex:
        try:
            form.append_assistant_message("BTP Assistant: [Fake proposal error] " + str(ex))
        except Exception:
            pass


if __name__ == "__main__":
    # ONE chat window, owned by Revit: stays with Revit, no taskbar entry, never topmost. The button shows / hides it.
    from System import AppDomain
    from System.Windows.Forms import NativeWindow
    _key = "BTP_CHAT_FORM"
    _existing = AppDomain.CurrentDomain.GetData(_key)
    if _existing is not None and not _existing.IsDisposed:
        if _existing.Visible:
            _existing.Hide()
        else:
            _existing.Show()
            _existing.Activate()
    else:
        _owner = NativeWindow()
        _owner.AssignHandle(__revit__.MainWindowHandle)
        chat = ChatForm()
        chat.ShowInTaskbar = False
        _show_fake_proposal_if_any(chat)
        chat.Show(_owner)
        AppDomain.CurrentDomain.SetData(_key, chat)

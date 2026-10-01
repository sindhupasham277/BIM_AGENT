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
    "answer": None
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


    # ========================================================
    # ENTER KEY → SEND
    # ========================================================

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
                "revit_btp_session",

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

chat = ChatForm()

chat.Show()
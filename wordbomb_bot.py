from __future__ import annotations

import queue
import random
import re
import threading
import time
import tkinter as tk
import unicodedata
import ctypes
from dataclasses import dataclass, field
from pathlib import Path

import easyocr
import keyboard
import mss
import numpy as np
import customtkinter as ctk
from wordfreq import top_n_list, zipf_frequency

PROMPT_WIDTH = 260
PROMPT_HEIGHT = 120
PROMPT_OFFSET_X = 0
PROMPT_OFFSET_X_RANKED = 140
PROMPT_OFFSET_Y = -320
TURN_BOX_EXTRA_H = 40

WORD_COUNT = 150000
WORD_LANGS = ("fr",)
REQUIRE_YOUR_TURN_TEXT_DEFAULT = False
DEBUG_OCR = False
MIN_FRAGMENT_LEN = 2
CANDIDATE_POOL = 64
RETRY_SAME_FRAGMENT_AFTER_S = 0.0
MAX_ATTEMPTS_PER_FRAGMENT = 4
FOCUS_CLICK_BEFORE_TYPING = True
FOCUS_CLICK_COOLDOWN_S = 0.0
FOCUS_CLICK_SETTLE_S = 0.0
STRICT_FRENCH_ONLY = True
FRENCH_MIN_ZIPF = 1.4
FRENCH_OVER_EN_MARGIN = 0.0
WORD_EDGE_DELAY_ENABLED = False
POST_SEND_LOOP_DELAY_S = 0.0
ACTIVE_POLL_SLEEP_S = 0.005
IDLE_POLL_SLEEP_S = 0.02
TURBO_TYPING_DEFAULT = True

DEFAULT_CHAR_DELAY_MS = 1
MIN_CHAR_DELAY_MS = 1
MAX_CHAR_DELAY_MS = 250
USE_SENDINPUT_TYPING = True

START_STOP_KEY = "f8"
QUIT_KEY = "f9"
KEEP_ON_TOP_DEFAULT = True

BLOCKED_WORDS_FILE = Path("blocked_names.txt")
EXTRA_WORDS_FILE = Path("extra_words.txt")

COMMON_FIRST_NAMES = {
    "adam",
    "adel",
    "adrien",
    "ahmed",
    "alex",
    "alexandre",
    "alice",
    "ali",
    "amanda",
    "amina",
    "amine",
    "ana",
    "andre",
    "andrea",
    "andrew",
    "anna",
    "anne",
    "anthony",
    "antoine",
    "arthur",
    "ayoub",
    "ben",
    "benjamin",
    "bruno",
    "camille",
    "carla",
    "carlos",
    "caroline",
    "charles",
    "charlie",
    "chloe",
    "chris",
    "christian",
    "christine",
    "claire",
    "clement",
    "daniel",
    "david",
    "denis",
    "dylan",
    "eddy",
    "edouard",
    "edward",
    "elias",
    "elise",
    "emma",
    "enzo",
    "eric",
    "eva",
    "fabien",
    "fatima",
    "felix",
    "florian",
    "franck",
    "francois",
    "gabriel",
    "gael",
    "george",
    "hugo",
    "ibrahim",
    "ines",
    "isabelle",
    "ivan",
    "jacob",
    "jade",
    "james",
    "jean",
    "jeanne",
    "jeff",
    "jeremy",
    "jessica",
    "john",
    "jonas",
    "jonathan",
    "jordan",
    "joseph",
    "jules",
    "julie",
    "julien",
    "justin",
    "karim",
    "kevin",
    "laura",
    "leo",
    "leon",
    "lina",
    "lisa",
    "louis",
    "luc",
    "lucas",
    "lucie",
    "mael",
    "manon",
    "marc",
    "margot",
    "maria",
    "marie",
    "marvin",
    "mathias",
    "mathieu",
    "mathis",
    "mehdi",
    "michael",
    "mohamed",
    "mohammed",
    "nabil",
    "nadia",
    "nathan",
    "noah",
    "nolan",
    "olivier",
    "omar",
    "paul",
    "pierre",
    "quentin",
    "rachid",
    "raphael",
    "rayane",
    "remi",
    "richard",
    "robin",
    "romain",
    "sabrina",
    "sam",
    "sami",
    "samir",
    "samuel",
    "sarah",
    "sofiane",
    "sophie",
    "steven",
    "theo",
    "thomas",
    "tom",
    "valentin",
    "victor",
    "vincent",
    "william",
    "yacine",
    "yanis",
    "yassine",
    "yohan",
    "youssef",
    "zoe",
}


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_word(word: str) -> str:
    return strip_accents(word).lower()


def is_french_enough(word: str) -> bool:
    if not STRICT_FRENCH_ONLY:
        return True
    fr_score = zipf_frequency(word, "fr")
    en_score = zipf_frequency(word, "en")

    if fr_score < FRENCH_MIN_ZIPF:
        return False

    if en_score > fr_score + FRENCH_OVER_EN_MARGIN and fr_score < 4.7:
        return False
    return True


def load_words() -> list[str]:
    seen: set[str] = set()
    words: list[str] = []
    for lang in WORD_LANGS:
        for raw in top_n_list(lang, WORD_COUNT):
            word = normalize_word(raw)
            if len(word) < 3:
                continue
            if not re.fullmatch(r"[a-z]+", word):
                continue
            if not is_french_enough(word):
                continue
            if word in seen:
                continue
            seen.add(word)
            words.append(word)
    if EXTRA_WORDS_FILE.exists():
        for line in EXTRA_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            word = normalize_word(line)
            if len(word) < 3 or not re.fullmatch(r"[a-z]+", word):
                continue
            if word in seen:
                continue
            seen.add(word)
            words.append(word)
    return words


def load_blocked_words() -> set[str]:
    blocked = {normalize_word(name) for name in COMMON_FIRST_NAMES}
    if BLOCKED_WORDS_FILE.exists():
        for line in BLOCKED_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            blocked.add(normalize_word(line))
    return blocked


def pick_word(fragment: str, words: list[str], blocked: set[str]) -> str | None:
    fragment = normalize_word(fragment)
    if len(fragment) < MIN_FRAGMENT_LEN:
        return None

    search_fragments = [fragment]
    if len(fragment) >= 4:
        search_fragments.extend([fragment[:3], fragment[-3:]])
    if len(fragment) >= 3:
        search_fragments.extend([fragment[:2], fragment[-2:]])

    search_fragments = list(dict.fromkeys(f for f in search_fragments if len(f) >= MIN_FRAGMENT_LEN))

    for frag in search_fragments:
        candidates: list[str] = []
        for word in words:
            if frag not in word:
                continue
            if word in blocked:
                continue
            if len(word) <= len(frag):
                continue
            if len(word) > 14:
                continue
            candidates.append(word)

        if candidates:
            candidates.sort(key=lambda w: (abs(len(w) - 7), len(w)))
            shortlist = candidates[:CANDIDATE_POOL]
            return random.choice(shortlist)

    return None


def build_capture_region(ranked_mode: bool = False) -> dict[str, int]:
    with mss.mss() as sct:
        mon = sct.monitors[1]
    center_x = mon["left"] + mon["width"] // 2
    center_y = mon["top"] + mon["height"] // 2
    height = PROMPT_HEIGHT + TURN_BOX_EXTRA_H
    offset_x = PROMPT_OFFSET_X_RANKED if ranked_mode else PROMPT_OFFSET_X
    return {
        "left": center_x + offset_x - PROMPT_WIDTH // 2,
        "top": center_y + PROMPT_OFFSET_Y - height // 2,
        "width": PROMPT_WIDTH,
        "height": height,
    }


def get_screen_center_point() -> tuple[int, int]:
    with mss.mss() as sct:
        mon = sct.monitors[1]
    center_x = mon["left"] + mon["width"] // 2
    center_y = mon["top"] + mon["height"] // 2
    return center_x, center_y


def click_point(x: int, y: int) -> bool:
    """Click at a screen coordinate and restore the mouse cursor position."""
    try:
        user32 = ctypes.windll.user32

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))

        user32.SetCursorPos(int(x), int(y))
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.01)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        user32.SetCursorPos(point.x, point.y)
        return True
    except Exception:
        return False


def preprocess_region(grab: mss.base.ScreenShot) -> np.ndarray:
    img = np.array(grab)[:, :, :3]
    gray = np.dot(img[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
    return np.where(gray > 145, 255, 0).astype(np.uint8)


def _normalize_ocr_caps(text: str) -> str:
    return text.upper().translate(str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B"}))


def _prompt_from_texts(texts: list[str]) -> tuple[str, str]:
    stopwords = {"YOUR", "TURN", "AUTO", "JOIN"}
    joined = _normalize_ocr_caps(" ".join(texts))
    matches = [m for m in re.findall(r"[A-Z]{2,4}", joined) if m not in stopwords]
    if not matches:
        return "", joined
    matches.sort(key=lambda m: (abs(len(m) - 3), len(m)))
    return matches[0], joined


def _upscale_binary(img: np.ndarray, factor: int = 2) -> np.ndarray:
    return np.repeat(np.repeat(img, factor, axis=0), factor, axis=1)


def extract_prompt_and_turn(
    reader: easyocr.Reader,
    sct: mss.mss,
    region: dict[str, int],
    require_turn_text: bool,
) -> tuple[str, bool, str]:
    proc = preprocess_region(sct.grab(region))

    prompt_crop = proc[:PROMPT_HEIGHT, :]
    prompt_texts = reader.readtext(
        prompt_crop,
        detail=0,
        paragraph=False,
        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
    letters, prompt_joined = _prompt_from_texts([str(t) for t in prompt_texts])

    if not letters or len(letters) > 4:
        prompt_big = _upscale_binary(prompt_crop, factor=2)
        prompt_texts_big = reader.readtext(
            prompt_big,
            detail=0,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        )
        letters_big, prompt_joined_big = _prompt_from_texts([str(t) for t in prompt_texts_big])
        if letters_big:
            letters = letters_big
            prompt_joined = prompt_joined_big

    full_joined = ""
    is_my_turn = True
    if require_turn_text:
        full_texts = reader.readtext(proc, detail=0, paragraph=False)
        full_joined = _normalize_ocr_caps(" ".join(str(t) for t in full_texts))
        is_my_turn = "YOUR" in full_joined

    debug_text = prompt_joined if not full_joined else f"{prompt_joined} | {full_joined}"
    return letters, is_my_turn, debug_text


def _sendinput_unicode_char(ch: str) -> bool:
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return False

    try:
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_UNICODE = 0x0004
        INPUT_KEYBOARD = 1

        ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]

        def send_key_event(vk: int, scan: int, flags: int) -> bool:
            inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan, flags, 0, 0))
            sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            return sent == 1

        code = ord(ch)
        if not send_key_event(0, code, KEYEVENTF_UNICODE):
            return False
        if not send_key_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            return False
        return True
    except Exception:
        return False


def _sendinput_enter() -> bool:
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return False

    try:
        KEYEVENTF_KEYUP = 0x0002
        VK_RETURN = 0x0D
        INPUT_KEYBOARD = 1
        ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]

        def send_key(vk: int, flags: int) -> bool:
            inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, flags, 0, 0))
            sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            return sent == 1

        return send_key(VK_RETURN, 0) and send_key(VK_RETURN, KEYEVENTF_KEYUP)
    except Exception:
        return False


def human_type_and_send(word: str, char_delay_ms: int) -> str:
    base = max(MIN_CHAR_DELAY_MS, int(char_delay_ms)) / 1000.0
    turbo_mode = int(char_delay_ms) <= 1
    if WORD_EDGE_DELAY_ENABLED:
        time.sleep(random.uniform(0.03, 0.11))

    used_sendinput = False
    if USE_SENDINPUT_TYPING:
        used_sendinput = True
        typed_count = 0
        for ch in word:
            if not _sendinput_unicode_char(ch):
                used_sendinput = False
                break
            typed_count += 1
            if turbo_mode:
                continue
            jitter = random.uniform(-0.35, 0.45) * base
            time.sleep(max(0.0, base + jitter))
        if used_sendinput:
            if WORD_EDGE_DELAY_ENABLED:
                time.sleep(random.uniform(0.03, 0.12))
            if _sendinput_enter():
                return "ok"
            used_sendinput = False
            if typed_count > 0:
                return "partial_fail"
        elif typed_count > 0:
            return "partial_fail"

    try:
        for ch in word:
            keyboard.write(ch, delay=0)
            if turbo_mode:
                continue
            jitter = random.uniform(-0.35, 0.45) * base
            time.sleep(max(0.0, base + jitter))
        if WORD_EDGE_DELAY_ENABLED:
            time.sleep(random.uniform(0.03, 0.12))
        keyboard.send("enter")
        return "ok"
    except Exception:
        return "none_fail"


@dataclass
class SharedState:
    running: bool = False
    char_delay_ms: int = DEFAULT_CHAR_DELAY_MS
    require_turn_text: bool = REQUIRE_YOUR_TURN_TEXT_DEFAULT
    keep_on_top: bool = KEEP_ON_TOP_DEFAULT
    ranked_mode: bool = False
    ui_focused: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def toggle_running(self) -> bool:
        with self.lock:
            self.running = not self.running
            return self.running

    def set_running(self, value: bool) -> None:
        with self.lock:
            self.running = value

    def set_char_delay_ms(self, value: int) -> None:
        with self.lock:
            self.char_delay_ms = max(MIN_CHAR_DELAY_MS, min(MAX_CHAR_DELAY_MS, value))

    def set_require_turn_text(self, value: bool) -> None:
        with self.lock:
            self.require_turn_text = value

    def set_keep_on_top(self, value: bool) -> None:
        with self.lock:
            self.keep_on_top = value

    def toggle_ranked_mode(self) -> bool:
        with self.lock:
            self.ranked_mode = not self.ranked_mode
            return self.ranked_mode

    def set_ranked_mode(self, value: bool) -> None:
        with self.lock:
            self.ranked_mode = value

    def set_ui_focused(self, value: bool) -> None:
        with self.lock:
            self.ui_focused = value

    def snapshot(self) -> tuple[bool, int, bool, bool, bool, bool]:
        with self.lock:
            return (
                self.running,
                self.char_delay_ms,
                self.require_turn_text,
                self.keep_on_top,
                self.ranked_mode,
                self.ui_focused,
            )


def qput(ui_queue: queue.Queue[tuple[str, str]], kind: str, payload: str) -> None:
    ui_queue.put((kind, payload))


def bot_worker(state: SharedState, ui_queue: queue.Queue[tuple[str, str]]) -> None:
    try:
        qput(ui_queue, "status", "Loading OCR model (FR)...")
        reader = easyocr.Reader(["fr"], gpu=False, verbose=False)
        qput(ui_queue, "status", "Loading words...")
        words = load_words()
        blocked = load_blocked_words()
        region = build_capture_region(ranked_mode=False)
        focus_point = get_screen_center_point()
        qput(ui_queue, "ready", f"{len(words)} words loaded, {len(blocked)} blocked")
        qput(ui_queue, "region", str(region))

        last_fragment = ""
        last_ocr = ""
        fragment_attempts = 0
        last_attempt_at = 0.0
        last_focus_click_at = 0.0
        last_suggested_word = ""
        ui_focus_warned = False
        last_ranked_mode = False
        start_pressed_prev = False
        quit_pressed_prev = False

        with mss.mss() as sct:
            while not state.stop_event.is_set():
                try:
                    start_pressed = keyboard.is_pressed(START_STOP_KEY)
                    quit_pressed = keyboard.is_pressed(QUIT_KEY)
                except Exception:
                    start_pressed = False
                    quit_pressed = False

                if quit_pressed and not quit_pressed_prev:
                    state.stop_event.set()
                    qput(ui_queue, "status", "Quit requested (F9)")
                    qput(ui_queue, "quit", "")
                    break
                if start_pressed and not start_pressed_prev:
                    running_now = state.toggle_running()
                    qput(ui_queue, "running", "ON" if running_now else "OFF")
                start_pressed_prev = start_pressed
                quit_pressed_prev = quit_pressed

                running, char_delay_ms, require_turn_text, _keep_on_top, ranked_mode, ui_focused = state.snapshot()
                if ranked_mode != last_ranked_mode:
                    region = build_capture_region(ranked_mode=ranked_mode)
                    last_ranked_mode = ranked_mode
                    qput(ui_queue, "region", str(region))
                    qput(ui_queue, "status", "Ranked mode ON" if ranked_mode else "Ranked mode OFF")
                if not running:
                    ui_focus_warned = False
                    time.sleep(IDLE_POLL_SLEEP_S)
                    continue

                fragment, is_my_turn_text, ocr_text = extract_prompt_and_turn(
                    reader, sct, region, require_turn_text=require_turn_text
                )

                if DEBUG_OCR and ocr_text and ocr_text != last_ocr:
                    qput(ui_queue, "ocr", ocr_text)
                    last_ocr = ocr_text

                if require_turn_text and not is_my_turn_text:
                    ui_focus_warned = False
                    time.sleep(ACTIVE_POLL_SLEEP_S)
                    continue

                if ui_focused:
                    if not ui_focus_warned:
                        qput(ui_queue, "status", "UI focused - click the game to let the bot type")
                        ui_focus_warned = True
                    time.sleep(ACTIVE_POLL_SLEEP_S)
                    continue
                ui_focus_warned = False

                if not fragment:
                    time.sleep(ACTIVE_POLL_SLEEP_S)
                    continue

                qput(ui_queue, "prompt", fragment)

                if fragment != last_fragment:
                    last_fragment = fragment
                    fragment_attempts = 0
                    last_attempt_at = 0.0
                    last_suggested_word = ""
                    qput(ui_queue, "typed", "-")
                else:
                    if fragment_attempts >= MAX_ATTEMPTS_PER_FRAGMENT:
                        time.sleep(ACTIVE_POLL_SLEEP_S)
                        continue
                    if time.time() - last_attempt_at < RETRY_SAME_FRAGMENT_AFTER_S:
                        time.sleep(ACTIVE_POLL_SLEEP_S)
                        continue

                word = pick_word(fragment, words, blocked)

                if not word:
                    if last_suggested_word != "(no match)":
                        qput(ui_queue, "selected", "-")
                        qput(ui_queue, "action", f"{fragment} -> no match (or filtered)")
                        last_suggested_word = "(no match)"
                    time.sleep(ACTIVE_POLL_SLEEP_S)
                    continue

                if word != last_suggested_word:
                    qput(ui_queue, "selected", word)
                qput(ui_queue, "action", f"{fragment} -> {word}")
                last_suggested_word = word
                fragment_attempts += 1
                last_attempt_at = time.time()

                if FOCUS_CLICK_BEFORE_TYPING and (time.time() - last_focus_click_at) >= FOCUS_CLICK_COOLDOWN_S:
                    if click_point(*focus_point):
                        last_focus_click_at = time.time()
                        if FOCUS_CLICK_SETTLE_S > 0:
                            time.sleep(FOCUS_CLICK_SETTLE_S)

                attempt_delay = char_delay_ms + max(0, (fragment_attempts - 1) * 20)
                try:
                    type_result = human_type_and_send(word, attempt_delay)
                    if type_result == "ok":
                        qput(ui_queue, "typed", word)
                    elif type_result == "partial_fail":
                        qput(ui_queue, "status", "Typing partially failed, retrying same prompt")
                        last_attempt_at = 0.0
                    else:
                        qput(ui_queue, "status", "Typing failed, retrying same prompt")
                        last_attempt_at = 0.0
                        time.sleep(0.01)
                        continue
                except Exception as exc:
                    qput(ui_queue, "status", f"Typing failed ({type(exc).__name__}), will retry")
                    last_attempt_at = 0.0
                if POST_SEND_LOOP_DELAY_S > 0:
                    time.sleep(POST_SEND_LOOP_DELAY_S)
    except Exception as exc:
        qput(ui_queue, "error", f"{type(exc).__name__}: {exc}")


def launch_ui() -> int:
    state = SharedState()
    ui_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("WordBot by Hypervisor")
    root.geometry("470x500")
    root.resizable(False, False)
    root.attributes("-topmost", KEEP_ON_TOP_DEFAULT)
    root.configure(fg_color="#0b1020")

    status_var = tk.StringVar(value="Booting...")
    speed_var = tk.DoubleVar(value=float(DEFAULT_CHAR_DELAY_MS))
    speed_label_var = tk.StringVar(value=f"{DEFAULT_CHAR_DELAY_MS} ms/char")
    ocr_var = tk.StringVar(value="-")
    prompt_var = tk.StringVar(value="-")
    selected_var = tk.StringVar(value="-")
    typed_var = tk.StringVar(value="-")
    action_var = tk.StringVar(value="-")
    info_var = tk.StringVar(value="Click the game input before starting")
    require_turn_var = tk.BooleanVar(value=REQUIRE_YOUR_TURN_TEXT_DEFAULT)
    topmost_var = tk.BooleanVar(value=KEEP_ON_TOP_DEFAULT)
    ranked_mode_var = tk.BooleanVar(value=False)

    colors = {
        "bg": "#0b1020",
        "panel": "#131b31",
        "panel_alt": "#10182b",
        "row": "#0f1629",
        "text": "#eaf0ff",
        "muted": "#95a6ce",
        "accent": "#4de2c5",
        "accent2": "#78a9ff",
        "warn": "#ffd166",
        "ok_bg": "#173b33",
        "ok_fg": "#55e7cb",
        "off_bg": "#3a2030",
        "off_fg": "#f2a1cf",
        "line": "#2a3959",
        "button_dark": "#1a233a",
        "button_dark_hover": "#22304f",
    }

    def on_toggle() -> None:
        running_now = state.toggle_running()
        apply_running_ui(running_now)

    def on_speed_change(value: float) -> None:
        speed = int(round(float(value)))
        state.set_char_delay_ms(speed)
        speed_label_var.set(f"{speed} ms/char")

    def on_turn_checkbox() -> None:
        state.set_require_turn_text(bool(require_turn_var.get()))

    def on_topmost_checkbox() -> None:
        keep = bool(topmost_var.get())
        state.set_keep_on_top(keep)
        try:
            root.attributes("-topmost", keep)
        except tk.TclError:
            pass

    def on_ranked_toggle() -> None:
        ranked_now = state.toggle_ranked_mode()
        ranked_mode_var.set(ranked_now)
        apply_ranked_ui(ranked_now)

    def on_hide() -> None:
        root.iconify()

    def on_close() -> None:
        state.stop_event.set()
        root.destroy()

    def make_value_row(parent: ctk.CTkFrame, label: str, variable: tk.StringVar, color: str) -> None:
        row = ctk.CTkFrame(parent, fg_color=colors["row"], corner_radius=10)
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(
            row,
            text=label,
            width=88,
            anchor="w",
            text_color=colors["muted"],
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(10, 4), pady=8)
        ctk.CTkLabel(
            row,
            textvariable=variable,
            anchor="w",
            text_color=color,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
        ).pack(side="left", fill="x", expand=True, padx=(4, 10), pady=8)

    shell = ctk.CTkFrame(root, fg_color="transparent")
    shell.pack(fill="both", expand=True, padx=10, pady=10)

    header = ctk.CTkFrame(shell, fg_color=colors["panel"], corner_radius=12)
    header.pack(fill="x")
    ctk.CTkLabel(
        header,
        text="WORDBOT BY HYPERVISOR",
        text_color=colors["text"],
        font=ctk.CTkFont(size=15, weight="bold"),
    ).pack(side="left", padx=12, pady=10)
    state_pill = ctk.CTkLabel(
        header,
        text="PAUSED",
        fg_color=colors["off_bg"],
        text_color=colors["off_fg"],
        corner_radius=999,
        font=ctk.CTkFont(size=12, weight="bold"),
        width=84,
        height=28,
    )
    state_pill.pack(side="right", padx=10, pady=9)

    controls = ctk.CTkFrame(shell, fg_color=colors["panel"], corner_radius=12)
    controls.pack(fill="x", pady=(8, 8))

    btn_row = ctk.CTkFrame(controls, fg_color="transparent")
    btn_row.pack(fill="x", padx=10, pady=(10, 6))
    toggle_btn = ctk.CTkButton(
        btn_row,
        text="Start",
        command=on_toggle,
        width=98,
        height=34,
        corner_radius=10,
        font=ctk.CTkFont(size=13, weight="bold"),
    )
    toggle_btn.pack(side="left")
    hide_btn = ctk.CTkButton(
        btn_row,
        text="Minimize",
        command=on_hide,
        width=90,
        height=34,
        corner_radius=10,
        fg_color=colors["button_dark"],
        hover_color=colors["button_dark_hover"],
        text_color=colors["text"],
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    hide_btn.pack(side="left", padx=(8, 0))
    ranked_btn = ctk.CTkButton(
        btn_row,
        text="Ranked Mode: OFF",
        command=on_ranked_toggle,
        width=132,
        height=34,
        corner_radius=10,
        fg_color=colors["button_dark"],
        hover_color=colors["button_dark_hover"],
        text_color=colors["text"],
        font=ctk.CTkFont(size=11, weight="bold"),
    )
    ranked_btn.pack(side="left", padx=(8, 0))
    ctk.CTkLabel(
        btn_row,
        text=f"{START_STOP_KEY.upper()} / {QUIT_KEY.upper()}",
        text_color=colors["muted"],
        font=ctk.CTkFont(family="Consolas", size=11),
    ).pack(side="right", pady=5)

    ctk.CTkLabel(
        controls,
        text="Typing speed",
        text_color=colors["text"],
        font=ctk.CTkFont(size=12, weight="bold"),
    ).pack(anchor="w", padx=12, pady=(2, 0))

    speed_slider = ctk.CTkSlider(
        controls,
        from_=MIN_CHAR_DELAY_MS,
        to=MAX_CHAR_DELAY_MS,
        variable=speed_var,
        command=on_speed_change,
        number_of_steps=MAX_CHAR_DELAY_MS - MIN_CHAR_DELAY_MS,
        progress_color=colors["accent2"],
        button_color=colors["accent2"],
        button_hover_color="#98bcff",
    )
    speed_slider.pack(fill="x", padx=12, pady=(6, 2))
    ctk.CTkLabel(
        controls,
        textvariable=speed_label_var,
        text_color=colors["muted"],
        font=ctk.CTkFont(size=12),
    ).pack(anchor="w", padx=12, pady=(0, 6))

    options_row = ctk.CTkFrame(controls, fg_color="transparent")
    options_row.pack(fill="x", padx=10, pady=(0, 10))

    turn_cb = ctk.CTkCheckBox(
        options_row,
        text='Require "YOUR TURN" text',
        variable=require_turn_var,
        command=on_turn_checkbox,
        text_color=colors["text"],
        fg_color=colors["accent2"],
        hover_color="#5f92ed",
        border_color=colors["line"],
        checkbox_width=18,
        checkbox_height=18,
    )
    turn_cb.pack(anchor="w")

    top_cb = ctk.CTkCheckBox(
        options_row,
        text="Keep window on top",
        variable=topmost_var,
        command=on_topmost_checkbox,
        text_color=colors["text"],
        fg_color=colors["accent"],
        hover_color="#35c9ad",
        border_color=colors["line"],
        checkbox_width=18,
        checkbox_height=18,
    )
    top_cb.pack(anchor="w", pady=(4, 0))

    live_panel = ctk.CTkFrame(shell, fg_color=colors["panel"], corner_radius=12)
    live_panel.pack(fill="x")
    ctk.CTkLabel(
        live_panel,
        text="Live",
        text_color=colors["text"],
        font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(anchor="w", padx=12, pady=(10, 4))
    make_value_row(live_panel, "Prompt", prompt_var, colors["accent2"])
    make_value_row(live_panel, "Selected", selected_var, colors["accent"])
    make_value_row(live_panel, "Last sent", typed_var, colors["warn"])
    make_value_row(live_panel, "OCR", ocr_var, colors["text"])
    make_value_row(live_panel, "Action", action_var, colors["muted"])

    status_panel = ctk.CTkFrame(shell, fg_color=colors["panel"], corner_radius=12)
    status_panel.pack(fill="x", pady=(8, 8))
    ctk.CTkLabel(
        status_panel,
        textvariable=status_var,
        text_color=colors["text"],
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(10, 2))
    ctk.CTkLabel(
        status_panel,
        textvariable=info_var,
        text_color=colors["muted"],
        font=ctk.CTkFont(size=11),
        justify="left",
        wraplength=430,
        anchor="w",
    ).pack(fill="x", padx=12, pady=(0, 10))

    log_panel = ctk.CTkFrame(shell, fg_color=colors["panel_alt"], corner_radius=12)
    log_panel.pack(fill="both", expand=True)
    ctk.CTkLabel(
        log_panel,
        text="Log",
        text_color=colors["text"],
        font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(anchor="w", padx=12, pady=(10, 6))
    log_text = ctk.CTkTextbox(
        log_panel,
        height=110,
        corner_radius=10,
        fg_color="#0a1224",
        text_color="#dbe7ff",
        font=ctk.CTkFont(family="Consolas", size=11),
        border_width=1,
        border_color=colors["line"],
    )
    log_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    log_text.configure(state="disabled")

    def append_log(message: str) -> None:
        ts = time.strftime("%H:%M:%S")
        log_text.configure(state="normal")
        log_text.insert("end", f"[{ts}] {message}\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    def apply_running_ui(is_running: bool) -> None:
        if is_running:
            state_pill.configure(text="RUNNING", fg_color=colors["ok_bg"], text_color=colors["ok_fg"])
            toggle_btn.configure(
                text="Stop",
                fg_color=colors["button_dark"],
                hover_color=colors["button_dark_hover"],
                text_color=colors["text"],
            )
            status_var.set("Bot active")
        else:
            state_pill.configure(text="PAUSED", fg_color=colors["off_bg"], text_color=colors["off_fg"])
            toggle_btn.configure(
                text="Start",
                fg_color=colors["accent"],
                hover_color="#35c9ad",
                text_color="#041612",
            )
            status_var.set("Bot paused")

    def apply_ranked_ui(is_ranked: bool) -> None:
        if is_ranked:
            ranked_btn.configure(
                text="Ranked Mode: ON",
                fg_color="#5b2dff",
                hover_color="#7248ff",
                text_color="#f2ecff",
            )
        else:
            ranked_btn.configure(
                text="Ranked Mode: OFF",
                fg_color=colors["button_dark"],
                hover_color=colors["button_dark_hover"],
                text_color=colors["text"],
            )

    apply_running_ui(False)
    apply_ranked_ui(False)

    def update_focus_flag() -> None:
        try:
            has_focus = root.state() != "iconic" and root.focus_displayof() is not None
            state.set_ui_focused(bool(has_focus))
        except tk.TclError:
            state.set_ui_focused(False)

    def poll_ui_queue() -> None:
        update_focus_flag()

        while True:
            try:
                kind, payload = ui_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "status":
                status_var.set(payload)
                append_log(payload)
            elif kind == "ready":
                status_var.set("Ready")
                info_var.set(payload)
                append_log(payload)
            elif kind == "region":
                append_log(f"OCR box: {payload}")
            elif kind == "running":
                apply_running_ui(payload == "ON")
                append_log(f"Bot {payload}")
            elif kind == "ocr":
                ocr_var.set(payload)
                if DEBUG_OCR:
                    append_log(f"OCR: {payload}")
            elif kind == "prompt":
                prompt_var.set(payload)
            elif kind == "selected":
                selected_var.set(payload)
            elif kind == "typed":
                typed_var.set(payload)
            elif kind == "action":
                action_var.set(payload)
                append_log(payload)
            elif kind == "error":
                status_var.set("Error")
                info_var.set(payload)
                append_log(f"ERROR: {payload}")
            elif kind == "quit":
                on_close()
                return

        if not state.stop_event.is_set():
            root.after(80, poll_ui_queue)

    worker = threading.Thread(target=bot_worker, args=(state, ui_queue), daemon=True)
    worker.start()

    root.bind("<Map>", lambda _e: update_focus_flag())
    root.bind("<Unmap>", lambda _e: state.set_ui_focused(False))
    root.bind("<FocusIn>", lambda _e: state.set_ui_focused(True))
    root.bind("<FocusOut>", lambda _e: update_focus_flag())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(80, poll_ui_queue)
    root.mainloop()
    return 0


def main() -> int:
    return launch_ui()


if __name__ == "__main__":
    raise SystemExit(main())

import sqlite3
import curses
from datetime import datetime

DB_FILE = "wsjtx_logs.db"
MY_CALL = "N1ZZT"
MY_GRID = "FN31"

FREQ_TO_BAND = [
    (1.800, 2.000, "160m"),
    (3.500, 4.000, "80m"),
    (5.250, 5.500, "60m"),
    (7.000, 7.300, "40m"),
    (10.100, 10.150, "30m"),
    (14.000, 14.350, "20m"),
    (18.068, 18.168, "17m"),
    (21.000, 21.450, "15m"),
    (24.890, 24.990, "12m"),
    (28.000, 29.700, "10m"),
    (50.000, 54.000, "6m"),
    (144.000, 148.000, "2m"),
]

BAND_COLORS = {
    "160m": curses.COLOR_MAGENTA,
    "80m": curses.COLOR_BLUE,
    "60m": curses.COLOR_CYAN,
    "40m": curses.COLOR_GREEN,
    "30m": curses.COLOR_YELLOW,
    "20m": curses.COLOR_RED,
    "17m": curses.COLOR_CYAN,
    "15m": curses.COLOR_GREEN,
    "12m": curses.COLOR_BLUE,
    "10m": curses.COLOR_YELLOW,
    "6m": curses.COLOR_MAGENTA,
    "2m": curses.COLOR_CYAN,
    "Unknown": curses.COLOR_WHITE
}

BAND_COLOR_PAIRS = {}


def get_band(freq):
    for low, high, band in FREQ_TO_BAND:
        if low <= freq <= high:
            return band
    return "Unknown"


def init_colors():
    curses.start_color()
    curses.use_default_colors()

    used_colors = set()
    pair_number = 1
    for band, color in BAND_COLORS.items():
        if color not in used_colors and pair_number < 64:  # Avoid exceeding COLOR_PAIRS
            curses.init_pair(pair_number, color, -1)
            BAND_COLOR_PAIRS[band] = curses.color_pair(pair_number)
            used_colors.add(color)
            pair_number += 1

    if pair_number + 3 < 64:
        curses.init_pair(pair_number, curses.COLOR_CYAN, -1)  # Sent reports
        BAND_COLOR_PAIRS['sent'] = curses.color_pair(pair_number)
        pair_number += 1
        curses.init_pair(pair_number, curses.COLOR_YELLOW, -1)  # Received reports
        BAND_COLOR_PAIRS['recv'] = curses.color_pair(pair_number)
        pair_number += 1
        curses.init_pair(pair_number, curses.COLOR_WHITE, -1)  # Low visibility (dim white)
        BAND_COLOR_PAIRS['low'] = curses.color_pair(pair_number)

def extract_qsos():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT
            CASE WHEN call1 = ? THEN call2 ELSE call1 END AS peer
        FROM logs
        WHERE call1 = ? OR call2 = ?
    ''', (MY_CALL, MY_CALL, MY_CALL))
    calls = [row[0] for row in c.fetchall() if row[0] is not None]

    all_qsos = []
    for call in calls:
        c.execute('''
            SELECT timestamp, frequency, msg FROM logs
            WHERE (call1 = ? AND call2 = ?) OR (call1 = ? AND call2 = ?)
            ORDER BY timestamp
        ''', (MY_CALL, call, call, MY_CALL))
        rows = c.fetchall()
        if not rows:
            continue

        current_qso = []
        prev_time = None
        for ts, freq, msg in rows:
            ts_dt = datetime.fromisoformat(ts)
            if not current_qso or (ts_dt - prev_time).seconds <= 60:
                current_qso.append((ts_dt, freq, msg))
            else:
                all_qsos.append((call, current_qso))
                current_qso = [(ts_dt, freq, msg)]
            prev_time = ts_dt

        if current_qso:
            all_qsos.append((call, current_qso))

    conn.close()
    return sorted(all_qsos, key=lambda x: x[1][0][0])


def format_time_range(start, end):
    return f"{start.strftime('%Y-%m-%d %H:%M:%S')} -> {end.strftime('%Y-%m-%d %H:%M:%S')}"


def draw_ui(stdscr):
    init_colors()

    curses.curs_set(0)
    stdscr.clear()
    stdscr.nodelay(False)
    stdscr.keypad(True)

    qsos = extract_qsos()
    filtered = qsos.copy()
    selected = 0
    offset = 0
    filter_call = ""
    filter_band = None
    expanded = set()

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        stdscr.addstr(0, 0, " QSO Log Viewer | '/' filter | b-band | ENTER-expand | PgUp/PgDn scroll | q-quit ")
        stdscr.hline(1, 0, '-', width)

        display = []
        for idx, (call, entries) in enumerate(filtered):
            start = entries[0][0]
            end = entries[-1][0]
            freq = round(entries[0][1], 3)
            band = get_band(freq)
            tokens = [token for _, _, msg in entries for token in msg.split() if token.upper().startswith(('R', '+', '-'))]
            reports = []
            for token in tokens:
                color = BAND_COLOR_PAIRS.get('recv') if token.startswith('R') else BAND_COLOR_PAIRS.get('sent')
                reports.append((token, color))
            display.append((call, band, freq, start, end, reports, entries))

        row_heights = [(1 + len(row[6]) if idx in expanded else 1) for idx, row in enumerate(display)]
        visible_rows = height - 3

        visible_height = 0
        for i in range(offset, len(display)):
            visible_height += row_heights[i]
            if visible_height >= visible_rows:
                break

        visible_top = offset
        visible_bottom = offset
        current_height = 0
        while visible_bottom < len(display) and current_height + row_heights[visible_bottom] <= visible_rows:
            current_height += row_heights[visible_bottom]
            visible_bottom += 1

        if selected < visible_top:
            offset = selected
        elif selected >= visible_bottom:
            while selected >= visible_bottom and visible_bottom < len(display):
                current_height -= row_heights[visible_top]
                visible_top += 1
                visible_bottom += 1
                offset = visible_top

        y = 2
        for idx in range(offset, len(display)):
            row = display[idx]
            highlight = curses.A_REVERSE if idx == selected else 0
            band_color = BAND_COLOR_PAIRS.get(row[1], curses.A_NORMAL)
            header = f" {row[0]:<8} | {row[1]:<4} | {row[2]:>7.3f} MHz | {format_time_range(row[3], row[4])} | "
            stdscr.addstr(y, 0, header, highlight)
            xpos = len(header)
            for token, color in row[5]:
                if xpos + len(token) + 1 >= width:
                    break
                stdscr.addstr(y, xpos, f"{token} ", color | highlight)
                xpos += len(token) + 1
            y += 1
            if idx in expanded:
                for ts, freq, msg in row[6]:
                    if y >= height - 1:
                        break
                    if msg.startswith("CQ") or msg.endswith(MY_GRID):
                        attr = BAND_COLOR_PAIRS.get('low') or curses.A_DIM
                    else:
                        attr = curses.A_NORMAL
                    stdscr.addstr(y, 2, f"[{ts}] {freq:.3f} MHz | {msg[:width-20]}", attr)
                    y += 1
            if y >= height - 1:
                break

        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif key == ord('/'):
            curses.echo()
            stdscr.addstr(height - 1, 0, "Filter callsign: ")
            stdscr.clrtoeol()
            filter_call = stdscr.getstr().decode().strip().upper()
            curses.noecho()
            filtered = [qso for qso in qsos if filter_call in qso[0]]
            selected = 0
            offset = 0
            expanded.clear()
        elif key == ord('b'):
            curses.echo()
            stdscr.addstr(height - 1, 0, "Filter band (e.g. 20m): ")
            stdscr.clrtoeol()
            filter_band = stdscr.getstr().decode().strip()
            curses.noecho()
            filtered = [qso for qso in qsos if get_band(qso[1][0][1]) == filter_band]
            selected = 0
            offset = 0
            expanded.clear()
        elif key == curses.KEY_DOWN and selected < len(filtered) - 1:
            selected += 1
        elif key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_NPAGE:
            for _ in range(visible_rows):
                if selected < len(filtered) - 1:
                    selected += 1
        elif key == curses.KEY_PPAGE:
            for _ in range(visible_rows):
                if selected > 0:
                    selected -= 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            if selected in expanded:
                expanded.remove(selected)
            else:
                expanded.add(selected)

curses.wrapper(draw_ui)



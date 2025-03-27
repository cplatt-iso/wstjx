import sqlite3
import argparse
from datetime import datetime, timedelta

DB_FILE = "wsjtx_logs.db"
MY_CALL = "N1ZZT"

# Heuristics to detect signal reports or QSO indicators
QSO_TERMS = {"RR73", "R73", "73"}
SIGNAL_REGEX = r"(R?[+-]?\d{2})"

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


def fetch_qsos(conn, target_call):
    c = conn.cursor()

    # Fetch all messages involving both your call and the target
    c.execute('''
        SELECT timestamp, frequency, msg, direction
        FROM logs
        WHERE (call1 = ? AND call2 = ?)
           OR (call1 = ? AND call2 = ?)
        ORDER BY timestamp
    ''', (MY_CALL, target_call, target_call, MY_CALL))

    rows = c.fetchall()
    return rows

def detect_qsos(messages):
    qsos = []
    current_qso = []
    prev_time = None
    threshold = timedelta(minutes=1)

    for ts_str, freq, msg, direction in messages:
        ts = datetime.fromisoformat(ts_str)
        if not current_qso or (ts - prev_time) <= threshold:
            current_qso.append((ts, freq, msg, direction))
        else:
            qsos.append(current_qso)
            current_qso = [(ts, freq, msg, direction)]
        prev_time = ts

    if current_qso:
        qsos.append(current_qso)

    return qsos

def extract_signal_reports(qso_msgs):
    reports = []
    for _, msg, _ in qso_msgs:
        tokens = msg.split()
        for token in tokens:
            if token in QSO_TERMS or token.startswith("R") or token.lstrip("+-").isdigit():
                reports.append(token)
    return reports

def get_band_from_freq(freq_mhz):
    for low, high, band in FREQ_TO_BAND:
        if low <= freq_mhz <= high:
            return band
    return "Unknown"

def extract_signal_reports(qso_msgs):
    reports = []
    for _, _, msg, _ in qso_msgs:
        tokens = msg.split()
        for token in tokens:
            if token in QSO_TERMS or token.startswith("R") or token.lstrip("+-").isdigit():
                reports.append(token)
    return reports

def most_common_freq(qso_msgs):
    freqs = [round(freq, 3) for _, freq, _, _ in qso_msgs]
    return max(set(freqs), key=freqs.count) if freqs else None

def print_qsos(qsos, target_call):
    if not qsos:
        print(f"No QSOs found with {target_call}.")
        return

    print(f"\nFound {len(qsos)} QSO(s) with {target_call}:\n")
    qsos.sort(key=lambda q: q[0][0])  # Sort by start timestamp (oldest to newest)
    for i, qso in enumerate(qsos, 1):
        start = qso[0][0]
        end = qso[-1][0]
        reports = extract_signal_reports(qso)
        freq = most_common_freq(qso)
        band = get_band_from_freq(freq) if freq else "Unknown"

        print(f"QSO #{i}")
        print(f"  Start Time (UTC): {start}")
        print(f"  End Time (UTC):   {end}")
        print(f"  Frequency: {freq:.3f} MHz")
        print(f"  Band: {band}")
        print(f"  Signal Reports / QSO Terms: {' '.join(reports) if reports else '(none found)'}")
        print("")

def dump_all_qsos(conn):
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT
            CASE
                WHEN call1 = ? THEN call2
                ELSE call1
            END AS peer
        FROM logs
        WHERE call1 = ? OR call2 = ?
    ''', (MY_CALL, MY_CALL, MY_CALL))

    calls = [row[0] for row in c.fetchall() if row[0] is not None]

    all_qsos = []

    for call in calls:
        messages = fetch_qsos(conn, call)
        qsos = detect_qsos(messages)

        for qso in qsos:
            start = qso[0][0]
            end = qso[-1][0]
            reports = extract_signal_reports(qso)
            freq = most_common_freq(qso)
            band = get_band_from_freq(freq) if freq else "Unknown"

            all_qsos.append({
                "call": call,
                "start": start,
                "end": end,
                "freq": freq,
                "band": band,
                "reports": reports
            })

    # ✅ Sort all QSOs by start time
    all_qsos.sort(key=lambda q: q["start"])

    for qso in all_qsos:
        print(f"QSO with {qso['call']:<8} | Band: {qso['band']:<4} | Freq: {qso['freq']:.3f} MHz | "
              f"Start: {qso['start']} | End: {qso['end']} | Reports: {' '.join(qso['reports']) if qso['reports'] else '—'}")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Dump all QSOs involving your callsign")
    parser.add_argument("callsign", nargs="?", help="Target callsign to search for (optional if --all is used)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_FILE)

    if args.all:
        dump_all_qsos(conn)
    elif args.callsign:
        target_call = args.callsign.strip().upper()
        messages = fetch_qsos(conn, target_call)
        qsos = detect_qsos(messages)
        print_qsos(qsos, target_call)
    else:
        print("Please provide a callsign or use --all to dump all QSOs.")

    conn.close()


if __name__ == "__main__":
    main()


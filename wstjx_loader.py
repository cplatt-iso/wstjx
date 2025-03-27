import sqlite3
import re
import os
from datetime import datetime
from time import time

DB_FILE = "wsjtx_logs.db"
LOG_FILE = "ALL.TXT"  # replace with your actual path
MY_CALL = "N1ZZT"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            frequency REAL,
            direction TEXT,
            snr INTEGER,
            delta REAL,
            dt INTEGER,
            msg TEXT,
            call1 TEXT,
            call2 TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS meta (
            log_file TEXT PRIMARY KEY,
            last_offset INTEGER
        )
    ''')

    # Indexes for fast lookups
    c.execute('CREATE INDEX IF NOT EXISTS idx_call1 ON logs(call1)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_call2 ON logs(call2)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON logs(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_calls_pair ON logs(call1, call2)')

    conn.commit()
    return conn

def get_last_offset(conn, filename):
    c = conn.cursor()
    c.execute('SELECT last_offset FROM meta WHERE log_file = ?', (filename,))
    row = c.fetchone()
    return row[0] if row else 0

def update_last_offset(conn, filename, offset):
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO meta (log_file, last_offset) VALUES (?, ?)', (filename, offset))
    conn.commit()

def parse_calls(msg):
    # Return up to 2 callsigns from message
    tokens = msg.split()
    calls = [t for t in tokens if re.match(r'^[A-Z0-9]{3,}$', t) and not t.isdigit()]
    if len(calls) >= 2:
        return calls[0], calls[1]
    elif len(calls) == 1:
        return calls[0], None
    return None, None

def parse_line(line):
    pattern = re.compile(r"(\d{6}_\d{6})\s+([\d\.]+)\s+(Rx|Tx)\s+FT8\s+([-+]?\d+)\s+([-+]?\d+\.\d+)\s+(\d+)\s+(.*)")
    match = pattern.match(line)
    if not match:
        return None
    ts, freq, direction, snr, delta, dt, msg = match.groups()
    timestamp = datetime.strptime(ts, "%y%m%d_%H%M%S")
    call1, call2 = parse_calls(msg)
    return (
        timestamp.isoformat(),
        float(freq),
        direction,
        int(snr),
        float(delta),
        int(dt),
        msg.strip(),
        call1,
        call2
    )
    
def process_log_file(conn, log_file):
    last_offset = get_last_offset(conn, log_file)
    total_size = os.path.getsize(log_file)

    print(f"Starting at offset {last_offset}, total size: {total_size}")
    inserts = []
    last_print_time = time()

    with open(log_file, "r") as f:
        f.seek(last_offset)
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break

            parsed = parse_line(line)
            if parsed:
                inserts.append(parsed)

            # Print progress every ~1 sec
            if time() - last_print_time >= 1:
                percent = (pos / total_size) * 100
                print(f"\rProgress: {percent:.2f}% ({pos}/{total_size} bytes)", end="")
                last_print_time = time()

            if len(inserts) >= 500:
                store_batch(conn, inserts)
                inserts = []

        # Final flush
        if inserts:
            store_batch(conn, inserts)

        update_last_offset(conn, log_file, f.tell())
        print("\nDone.")

def store_batch(conn, batch):
    c = conn.cursor()
    c.executemany('''
        INSERT INTO logs (
            timestamp, frequency, direction, snr, delta, dt, msg, call1, call2
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', batch)
    conn.commit()

def main():
    conn = init_db()
    process_log_file(conn, LOG_FILE)
    conn.close()

if __name__ == "__main__":
    main()


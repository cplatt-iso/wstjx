# WSJTX Log Tools

This repository contains tools for managing, parsing, and interactively exploring WSJT-X FT8 logs. It includes two main scripts:

- `viewer.py`: An interactive curses-based TUI to explore confirmed QSOs from the logs.
- `wstjx_loader.py`: A parser and database loader for raw WSJT-X log files.

---

## 🐍 `wstjx_loader.py`

This script parses WSJT-X FT8 log lines and stores them in a SQLite database (`wsjtx_logs.db`). It supports incremental parsing (won't re-import the same lines).

### Features
- Parses standard WSJT-X FT8 log output (from file or stdin).
- Extracts timestamps, frequency, callsigns, and FT8 messages.
- Supports resuming from the last processed line.
- Populates a normalized SQLite database for querying.

### Usage
```bash
python3 wstjx_loader.py /path/to/your.log
```

### Database Schema (simplified)
- `logs` table:
  - `timestamp` (UTC datetime)
  - `frequency` (MHz)
  - `call1`, `call2` (callsigns involved)
  - `msg` (raw FT8 message)

---

## 📺 `viewer.py`

An interactive text-based UI (TUI) for exploring confirmed QSOs using the parsed logs.

### Features
- Interactive keyboard navigation
- Inline expansion of QSOs with full message details
- Call and band filtering
- Colored output:
  - Bands
  - Sent/received signal reports
  - Low-importance messages like CQ

### Usage
```bash
python3 viewer.py
```

### Keyboard Shortcuts
| Key        | Action                          |
|------------|----------------------------------|
| `↑ ↓`      | Navigate QSOs                    |
| `PgUp/PgDn`| Scroll by page                   |
| `Enter`    | Expand/collapse QSO              |
| `/`        | Filter by callsign               |
| `b`        | Filter by band                   |
| `q`        | Quit viewer                      |

---

## 📂 Example Log Line
```
250327_025730    14.074 Rx FT8      6  0.4 1014 WQ1I K0BF RR73
```
Parsed into:
- Time: `2025-03-27 02:57:30`
- Frequency: `14.074 MHz`
- Calls: `WQ1I` and `K0BF`
- Message: `RR73`

---

## 📝 Requirements
- Python 3.8+
- Standard libraries only (`sqlite3`, `curses`, `datetime`)

> Note: `curses` support on Windows may require WSL or a terminal emulator like MobaXTerm.

---

## 📈 Roadmap Ideas
- Export selected QSO to ADIF or JSON
- Integration with QRZ lookups
- More advanced filtering (DXCC, grid square)
- Theme support (light/dark mode)

---

## 📖 License
MIT License

---

Questions? Ideas? Feel free to open an issue or fork and contribute!



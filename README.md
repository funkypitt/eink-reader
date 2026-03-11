# eInk Reader

An eInk-optimized ebook reader for Linux, forked from [Lector](https://github.com/BasioMeusPuga/Lector). Designed for the Lenovo ThinkBook Plus Gen 4 eInk display with [Tinta4PlusU](https://github.com/funkypitt/Tinta4Plus-Universal) integration.

## What it does

- **Page mode only** — no scroll mode, only clean page turns (single page or double page)
- **Automatic eInk refresh** — after every page turn, sends a "clear ghosts" command to the Tinta4PlusU helper daemon via Unix socket, eliminating ghosting artifacts
- **Works when Tinta4PlusU is running** — if the helper daemon isn't active, the reader works normally without refresh

## Supported formats

- EPUB
- MOBI
- PDF
- CBR / CBZ (comics)
- DJVU
- FB2
- Markdown
- Plain text

## Requirements

- Python 3.6+
- PyQt5
- beautifulsoup4
- lxml
- PyMuPDF (for PDF support)
- python-djvulibre (optional, for DJVU)
- [Tinta4PlusU](https://github.com/funkypitt/Tinta4Plus-Universal) helper daemon running (for eInk refresh)

## Install

### Using the installer (recommended)

```bash
sudo bash installer.sh
```

This handles everything: apt packages, pip packages (PyMuPDF), app files to `/opt/eink-reader`, launcher in `/usr/local/bin/eink-reader`, desktop entry, and icon.

To uninstall:
```bash
sudo bash installer.sh --uninstall
```

### Manual install

```bash
# Install system dependencies
sudo apt install python3-pyqt5 python3-lxml python3-bs4

# Install Python dependencies
pip3 install pymupdf

# Run directly
python3 -m lector

# Or install
pip3 install .
```

## Usage

1. Start Tinta4PlusU and enable the eInk display
2. Launch the reader: `eink-reader` (or `python3 -m lector` if running from source)
3. Add books to the library (drag & drop or File > Add)
4. Open a book — it opens in **page mode** by default
5. Navigate with **Up/Down arrows**, **mouse wheel**, or **Left/Right arrows** (chapter change)
6. Each page turn automatically triggers an eInk refresh to clear ghosting

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| Up / Down | Previous / Next page |
| Left / Right | Previous / Next chapter |
| Space | Next page (large step) |
| F | Toggle fullscreen |
| Escape | Exit fullscreen |
| Ctrl+B | Bookmarks |
| Ctrl+F | Search |

## How the eInk refresh works

The reader communicates with the Tinta4PlusU helper daemon via a Unix socket at `/tmp/tinta4plusu.sock`. After each page turn, it sends a `refresh-eink` JSON command in a background thread (non-blocking). If the daemon isn't running, the refresh is silently skipped.

## Credits

- Based on [Lector](https://github.com/BasioMeusPuga/Lector) by BasioMeusPuga (GPLv3)
- eInk integration with [Tinta4PlusU](https://github.com/funkypitt/Tinta4Plus-Universal)

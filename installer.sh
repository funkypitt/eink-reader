#!/bin/bash
set -eE

# eInk Reader Installer
# Installs the eInk-optimized ebook reader (Lector fork + Tinta4PlusU integration)

APP_NAME="eink-reader"
INSTALL_DIR="/opt/eink-reader"
BIN_DIR="/usr/local/bin"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons/hicolor/512x512/apps"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/eink-reader-install.log"
CURRENT_STEP=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; echo "[INFO] $1" >> "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; echo "[WARN] $1" >> "$LOG_FILE"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; echo "[ERROR] $1" >> "$LOG_FILE"; }

# ─── Error trap ──────────────────────────────────────────────────────────────

on_error() {
    local exit_code=$?
    local line_no=$1
    echo ""
    error "Installation failed at line ${line_no} (exit code ${exit_code})"
    if [ -n "$CURRENT_STEP" ]; then
        error "During step: ${CURRENT_STEP}"
    fi
    error "See full log: ${LOG_FILE}"
    echo ""
    error "You can retry the installation after fixing the issue."
    error "To clean up a partial install: sudo bash installer.sh --uninstall"
    exit "$exit_code"
}

trap 'on_error ${LINENO}' ERR

step() {
    CURRENT_STEP="$1"
    info "$1"
}

# ─── Uninstall ───────────────────────────────────────────────────────────────

do_uninstall() {
    info "Uninstalling eInk Reader..."

    rm -f  "${BIN_DIR}/eink-reader"
    rm -rf "${INSTALL_DIR}"
    rm -f  "${DESKTOP_DIR}/eink-reader.desktop"
    rm -f  "${ICON_DIR}/eink-reader.png"

    info "eInk Reader has been uninstalled."
    exit 0
}

# ─── Check prerequisites ────────────────────────────────────────────────────

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        error "This installer must be run as root (sudo bash installer.sh)"
        exit 1
    fi
}

# ─── Install system dependencies ────────────────────────────────────────────

install_deps() {
    step "Installing system dependencies"

    local pkgs="python3 python3-pyqt5 python3-lxml python3-bs4 python3-xmltodict"

    if ! apt-get update -qq >> "$LOG_FILE" 2>&1; then
        error "apt-get update failed. Check your internet connection and sources."
        error "See: ${LOG_FILE}"
        exit 1
    fi

    if ! apt-get install -y -qq $pkgs >> "$LOG_FILE" 2>&1; then
        error "apt-get install failed for packages: ${pkgs}"
        error "See: ${LOG_FILE}"
        exit 1
    fi
    info "APT packages installed: ${pkgs}"

    # Install pip packages not available in apt
    step "Installing Python pip packages (PyMuPDF)"
    local pip_cmd="pip3"
    if ! command -v pip3 &>/dev/null; then
        apt-get install -y -qq python3-pip >> "$LOG_FILE" 2>&1
    fi
    if $pip_cmd install --break-system-packages pymupdf >> "$LOG_FILE" 2>&1; then
        info "pip packages installed (pymupdf)."
    elif $pip_cmd install pymupdf >> "$LOG_FILE" 2>&1; then
        info "pip packages installed (pymupdf)."
    else
        warn "pip install failed for pymupdf. PDF support will not be available."
        warn "You can install it manually: pip3 install pymupdf"
        warn "See: ${LOG_FILE}"
    fi
}

# ─── Verify dependencies ────────────────────────────────────────────────────

check_deps() {
    info "Verifying dependencies..."
    local missing=()

    if ! command -v python3 &>/dev/null; then
        missing+=("python3 (apt)")
    else
        for mod_pkg in "PyQt5:python3-pyqt5" "lxml:python3-lxml" "bs4:python3-bs4" "xmltodict:python3-xmltodict" "fitz:pymupdf (pip3)"; do
            local mod="${mod_pkg%%:*}"
            local pkg="${mod_pkg##*:}"
            if ! python3 -c "import $mod" 2>/dev/null; then
                missing+=("$pkg")
            fi
        done
    fi

    if [ ${#missing[@]} -eq 0 ]; then
        info "All dependencies OK."
    else
        echo ""
        warn "Missing dependencies:"
        for dep in "${missing[@]}"; do
            echo -e "  ${YELLOW}!${NC} ${dep}"
        done
        echo ""
        warn "The application may not work fully until these are installed."
    fi
}

# ─── Install application ────────────────────────────────────────────────────

install_app() {
    step "Installing eInk Reader to ${INSTALL_DIR}"

    # Check source files exist
    if [ ! -d "${SCRIPT_DIR}/lector" ]; then
        error "lector/ directory not found in ${SCRIPT_DIR}"
        error "Run this installer from the eink-reader repository root."
        exit 1
    fi

    mkdir -p "${INSTALL_DIR}"

    # Copy the lector package
    cp -r "${SCRIPT_DIR}/lector" "${INSTALL_DIR}/"
    info "Application files copied."

    # Copy setup files for potential pip install later
    for f in setup.py setup.cfg requirements.txt; do
        [ -f "${SCRIPT_DIR}/${f}" ] && cp "${SCRIPT_DIR}/${f}" "${INSTALL_DIR}/"
    done

    # Create launcher script
    cat > "${BIN_DIR}/eink-reader" << 'WRAPPER'
#!/bin/bash
export PYTHONPATH="/opt/eink-reader:${PYTHONPATH}"
exec python3 -m lector "$@"
WRAPPER
    chmod 755 "${BIN_DIR}/eink-reader"

    info "Launcher installed: ${BIN_DIR}/eink-reader"
}

# ─── Install desktop entry & icon ───────────────────────────────────────────

install_desktop() {
    step "Installing desktop entry and icon"

    # Desktop entry
    cp "${SCRIPT_DIR}/eink-reader.desktop" "${DESKTOP_DIR}/"

    # Icon (reuse Lector icon)
    mkdir -p "${ICON_DIR}"
    cp "${SCRIPT_DIR}/lector/resources/raw/Lector.png" "${ICON_DIR}/eink-reader.png"

    # Update desktop database
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
    fi

    # Update icon cache
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
    fi

    info "Desktop entry and icon installed."
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
    # Initialize log file
    echo "=== eInk Reader Installer — $(date) ===" > "$LOG_FILE"

    echo ""
    echo "╔══════════════════════════════════════╗"
    echo "║       eInk Reader Installer          ║"
    echo "║  Lector fork + Tinta4PlusU refresh   ║"
    echo "╚══════════════════════════════════════╝"
    echo ""

    # Handle --uninstall
    if [ "${1}" = "--uninstall" ]; then
        check_root
        do_uninstall
    fi

    check_root
    install_deps
    install_app
    install_desktop
    check_deps

    echo ""
    info "════════════════════════════════════════"
    info " Installation complete!"
    info ""
    info " Launch from terminal:  eink-reader"
    info " Or find 'eInk Reader' in your application menu."
    info ""
    info " For eInk refresh on page turns, make sure"
    info " Tinta4PlusU is running with the eInk enabled."
    info ""
    info " To uninstall:  sudo bash installer.sh --uninstall"
    info " Install log:   ${LOG_FILE}"
    info "════════════════════════════════════════"
    echo ""
}

main "$@"

#!/bin/sh
# Vendored from GalaxyBlockchainEngineering/staking_agent docker/rootfs.sh at commit db88c9cb267a2f8e796237d774ca91ebbdc58ad7,
# adapted: no state dir (the only writable path is /tmp; the charts mount /data), app user home /tmp.
# Runs in the alpine builder. Assembles the complete runtime filesystem for the FROM scratch image in $1:
# the Python interpreter + trimmed stdlib, the venv, and exactly the shared libraries those ELF files load
# (resolved with ldd, so a new or dropped native dependency changes the list with no edit here), plus CA
# certificates, the UTC zoneinfo, passwd/group for the app user and /tmp. The app code (/src) is root-owned and
# read-only to the app user; the only writable path is /tmp.
# Usage: rootfs.sh <root> <ca-bundle> <uid> <gid>
set -eu

ROOT="${1:?root}"
CA_BUNDLE="${2:?ca bundle}"
APP_UID="${3:?uid}"
APP_GID="${4:?gid}"
PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
VENV=/opt/venv

mkdir -p "$ROOT/usr/local/bin" "$ROOT/usr/local/lib" "$ROOT/etc/ssl/certs" "$ROOT/opt"

# Interpreter (python:alpine builds it with --enable-shared, so libpython is resolved by ldd below).
cp -a "/usr/local/bin/python$PYVER" "$ROOT/usr/local/bin/"
ln -s "python$PYVER" "$ROOT/usr/local/bin/python3"
ln -s python3 "$ROOT/usr/local/bin/python"

# Stdlib without what this CLI never uses: the system site-packages (pip/setuptools), tests, IDLE, Tk,
# ensurepip, the static libpython/Makefile (config-*), and the interactive/terminal, dbm and sqlite3 extensions,
# which only exist to pull ncurses/readline/gdbm/sqlite into the image (the CLI is Postgres-only).
cp -a "/usr/local/lib/python$PYVER" "$ROOT/usr/local/lib/"
STDLIB="$ROOT/usr/local/lib/python$PYVER"
rm -rf "$STDLIB/site-packages" "$STDLIB/test" "$STDLIB/idlelib" "$STDLIB/tkinter" "$STDLIB/turtledemo" \
  "$STDLIB/turtle.py" "$STDLIB/ensurepip" "$STDLIB/curses" "$STDLIB/sqlite3" "$STDLIB/dbm/sqlite3.py" \
  "$STDLIB/lib-dynload"/_sqlite3*.so "$STDLIB"/config-"$PYVER"-* "$STDLIB/lib-dynload"/_test*.so \
  "$STDLIB/lib-dynload"/_ctypes_test*.so "$STDLIB/lib-dynload"/_xxtestfuzz*.so "$STDLIB/lib-dynload"/xx*.so "$STDLIB/lib-dynload"/_curses*.so \
  "$STDLIB/lib-dynload"/readline*.so "$STDLIB/lib-dynload"/_gdbm*.so "$STDLIB/lib-dynload"/_dbm*.so \
  "$STDLIB/lib-dynload"/_tkinter*.so
find "$STDLIB" -depth -type d \( -name test -o -name tests -o -name idle_test \) -exec rm -rf {} +
mkdir -p "$STDLIB/site-packages"

# Venv: only the interpreter links and site-packages (activate scripts need a shell, and dependency console scripts
# have an interpreter shebang nothing here uses; the image runs /src/main.py).
cp -a "$VENV" "$ROOT/opt/"
find "$ROOT$VENV/bin" -mindepth 1 ! -name 'python*' -exec rm -rf {} +

# Shared libraries: everything ldd resolves for every ELF in the root, copied to the path the loader found
# it at. Libraries already inside the root are left where they are. Wheel-vendored libraries (*.libs/, from
# auditwheel) have no RPATH of their own and are only loadable through the extension that needs them, so
# they are resolved through that extension rather than on their own.
needed="$(mktemp)"
find "$ROOT" -type f ! -path '*.libs/*' | while read -r f; do
  [ -n "$(scanelf -B -F '%F' "$f" 2>/dev/null)" ] || continue
  # musl's ldd exits non-zero on the Python C-API symbols an extension leaves to the interpreter; those are
  # expected. A library it cannot find is not.
  out="$(ldd "$f" 2>&1 || true)"
  if echo "$out" | grep -q 'Error loading shared library'; then echo "unresolved library in $f:" >&2; echo "$out" | grep 'Error loading' >&2; exit 1; fi
  echo "$out" | awk '$2 == "=>" { print $1, $3 } $1 ~ /^\// { print "-", $1 }' >>"$needed"
done
sort -u "$needed" | while read -r soname path; do
  case "$path" in "$ROOT"/*) continue ;; esac
  [ -e "$ROOT$path" ] || { mkdir -p "$ROOT$(dirname "$path")"; cp -L "$path" "$ROOT$path"; }
  if [ "$soname" != - ] && [ "$soname" != "$(basename "$path")" ] && [ ! -e "$ROOT$(dirname "$path")/$soname" ]; then
    ln -s "$(basename "$path")" "$ROOT$(dirname "$path")/$soname"
  fi
done
rm -f "$needed"

# Keep the shipped OS packages visible to scanners: os-release plus an apk database with only the packages
# that own a file copied above (not the builder's full package list, which is not in the image).
cp -L /etc/os-release "$ROOT/etc/os-release"
cp /etc/alpine-release "$ROOT/etc/alpine-release"
cp "$CA_BUNDLE" "$ROOT/etc/ssl/certs/ca-certificates.crt"
# UTC only (zoneinfo / botocore timestamps); other zones are not needed.
mkdir -p "$ROOT/usr/share/zoneinfo"
cp -L /usr/share/zoneinfo/UTC "$ROOT/usr/share/zoneinfo/UTC"
ln -s certs/ca-certificates.crt "$ROOT/etc/ssl/cert.pem"
pkgs="$( (cd "$ROOT" && find lib usr/lib -type f 2>/dev/null) | sed 's|^|/|' | xargs -r apk info -q --who-owns 2>/dev/null | sort -u | tr '\n' ' ')"
pkgs="$pkgs$(apk info -q --who-owns /etc/ssl/certs/ca-certificates.crt /usr/share/zoneinfo/UTC 2>/dev/null | sort -u | tr '\n' ' ')"
mkdir -p "$ROOT/lib/apk/db"
awk -v want=" $pkgs " 'BEGIN { RS = ""; ORS = "\n\n" } { for (i = 1; i <= NF; i++) if ($i ~ /^P:/) { if (index(want, " " substr($i, 3) " ")) print; break } }' \
  /lib/apk/db/installed >"$ROOT/lib/apk/db/installed"

printf 'root:x:0:0:root:/root:/sbin/nologin\nappuser:x:%s:%s:appuser:/tmp:/sbin/nologin\n' "$APP_UID" "$APP_GID" >"$ROOT/etc/passwd"
printf 'root:x:0:\nappuser:x:%s:\n' "$APP_GID" >"$ROOT/etc/group"
mkdir -p "$ROOT/tmp"
chmod 1777 "$ROOT/tmp"

echo "runtime libraries:"; (cd "$ROOT" && find lib usr/lib -name '*.so*' 2>/dev/null | sort)
echo "apk packages recorded: $pkgs"

#!/bin/zsh
# PopClip starts external scripts with a minimal PATH. Locate an installed
# Python explicitly; never install dependencies or run user shell startup files.
# PopClip sets the working directory to the package root for file_ops.py.
set -eu

for python_bin in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  [[ -x "$python_bin" ]] || continue
  # /usr/bin/python3 may be a Command Line Tools stub. Avoid its installer UI.
  if [[ "$python_bin" == /usr/bin/python3 ]] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
    continue
  fi
  if "$python_bin" -I -X utf8 -c 'import sys; sys.exit(sys.version_info < (3, 9))' </dev/null >/dev/null 2>&1; then
    exec "$python_bin" -I -X utf8 "$@"
  fi
done

print -r -- '{"ok":false,"errorCode":"missing_python"}'
exit 127

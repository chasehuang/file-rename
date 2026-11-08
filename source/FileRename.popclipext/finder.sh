#!/bin/zsh
set -eu

# Read the selected item's URL without coercing it to an alias.
exec /usr/bin/osascript - <<'APPLESCRIPT'
on run
  try
    tell application id "com.apple.finder"
      set selectedItems to selection as list
      if (count of selectedItems) is not 1 then return "ERR:SELECTION"
      set selectedURL to URL of (item 1 of selectedItems)
    end tell
    if selectedURL is missing value or selectedURL is "" then return "ERR:FINDER"
    return "OK:" & selectedURL
  on error number errorNumber
    if errorNumber is -1743 then return "ERR:PERMISSION"
    return "ERR:FINDER"
  end try
end run
APPLESCRIPT

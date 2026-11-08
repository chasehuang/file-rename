#!/bin/zsh
set -eu

# Text reaches AppleScript only as data, never as interpolated source.
exec /usr/bin/osascript - "$1" "$2" "$3" <<'APPLESCRIPT'
on run argv
  set dialogTitle to item 1 of argv
  set dialogPrompt to item 2 of argv
  set proposedName to item 3 of argv
  try
    set answer to display dialog dialogPrompt default answer proposedName with title dialogTitle buttons {"Cancel", "Apply"} default button "Apply" cancel button "Cancel"
    return "APPLY:" & (text returned of answer)
  on error number errorNumber
    if errorNumber is -128 then return "CANCEL"
    error number errorNumber
  end try
end run
APPLESCRIPT

!include "FileFunc.nsh"
!include "LogicLib.nsh"

; Keep a selected drive root from becoming the application directory itself.
; For example, choosing E:\ installs to E:\PaperSage instead of cluttering E:\.
!macro customPageAfterChangeDir
  Function .onVerifyInstDir
    ${GetRoot} "$INSTDIR" $0
    ${If} "$INSTDIR" == "$0"
      ; GetRoot returns a local drive root without its trailing backslash
      ; (for example, E:). Add the separator explicitly: otherwise
      ; E:PaperSage is drive-relative instead of the intended E:\PaperSage.
      StrCpy $INSTDIR "$0\PaperSage"
    ${EndIf}
  FunctionEnd
!macroend

; Silent updates (auto-update always installs silently) die in the built-in
; "uninstall old version" step when the previously installed build shipped an
; uninstaller from an older NSIS generation: ExecWait reports 2 and the whole
; update aborts. Heal it here instead: in silent mode only, run the previous
; uninstaller synchronously with the directory pin (the mode that reliably
; works) and clear its registration, so the installer proceeds as a fresh
; install instead of delegating to the incompatible built-in step.
!macro customInit
  IfSilent 0 silentUninstallDone
    ReadRegStr $R0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTALL_APP_KEY}" "UninstallString"
    ${If} $R0 != ""
      ; UninstallString is "<installDir>\Uninstall PaperSage.exe" /currentuser.
      StrCpy $R1 $R0 "" 1
      StrLen $R2 $R1
      StrCpy $R3 0
      ${Do}
        StrCpy $R4 $R1 1 $R3
        ${If} $R4 == '"'
          ${Break}
        ${EndIf}
        IntOp $R3 $R3 + 1
      ${LoopUntil} $R3 >= $R2
      StrCpy $R5 $R1 $R3
      ${GetParent} $R5 $R6
      IfFileExists "$R5" 0 silentUninstallSkip
        ClearErrors
        ExecWait '"$R5" /S _?=$R6' $R7
        ; Best effort: even a failed old uninstaller must not wedge the
        ; update; dropping the registration makes this a fresh install.
        DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTALL_APP_KEY}"
        StrCpy $INSTDIR $R6
    ${EndIf}
  silentUninstallSkip:
  silentUninstallDone:
!macroend

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

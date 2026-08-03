!include "FileFunc.nsh"

; Keep a selected drive root from becoming the application directory itself.
; For example, choosing E:\ installs to E:\PaperSage instead of cluttering E:\.
!macro customPageAfterChangeDir
  Function .onVerifyInstDir
    ${GetRoot} "$INSTDIR" $0
    ${If} "$INSTDIR" == "$0"
      ; GetRoot returns a drive root with its trailing backslash, so this
      ; always produces an absolute path such as E:\PaperSage.
      StrCpy $INSTDIR "$0PaperSage"
    ${EndIf}
  FunctionEnd
!macroend

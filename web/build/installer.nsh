!include "FileFunc.nsh"

; Keep a selected drive root from becoming the application directory itself.
; For example, choosing E:\ installs to E:\PaperSage instead of cluttering E:\.
!macro customPageAfterChangeDir
  Function .onVerifyInstDir
    ${GetRoot} "$INSTDIR" $0
    ${If} "$INSTDIR" == "$0"
      StrCpy $INSTDIR "$INSTDIRPaperSage"
    ${EndIf}
  FunctionEnd
!macroend

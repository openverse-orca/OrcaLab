; OrcaLab Windows Installer
; Built with NSIS (makensis), compatible with Linux CI

Unicode true
SetCompressor /SOLID lzma

!define PRODUCT_NAME "OrcaLab"
!define PRODUCT_VERSION "26.4.3"
!define PRODUCT_PUBLISHER "松应科技"
!define PRODUCT_WEB_SITE "https://orca3d.cn"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\orcalab.bat"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\..\dist\OrcaLab-${PRODUCT_VERSION}-Setup.exe"
InstallDir "$PROGRAMFILES\OrcaLab"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
RequestExecutionLevel admin

VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "LegalCopyright" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "OrcaLab Installer"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"

; ── Interface ───────────────────────────────────────────
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "..\..\orcalab\assets\icons\orcalab_logo.ico"
!define MUI_UNICON "..\..\orcalab\assets\icons\orcalab_logo.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; ── Install Section ─────────────────────────────────────
Section "Install"
    SetOutPath "$INSTDIR"

    File "orcalab.bat"
    File "..\..\orcalab\assets\icons\orcalab_logo.ico"

    ; Desktop shortcut
    CreateShortCut "$DESKTOP\OrcaLab.lnk" "$INSTDIR\orcalab.bat" "" "$INSTDIR\orcalab_logo.ico"

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\OrcaLab"
    CreateShortCut "$SMPROGRAMS\OrcaLab\OrcaLab.lnk" "$INSTDIR\orcalab.bat" "" "$INSTDIR\orcalab_logo.ico"
    CreateShortCut "$SMPROGRAMS\OrcaLab\Uninstall.lnk" "$INSTDIR\uninst.exe"

    ; Registry for Add/Remove Programs
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\orcalab_logo.ico"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoRepair" 1

    ; Uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

; ── Uninstall Section ───────────────────────────────────
Section "Uninstall"
    Delete "$INSTDIR\orcalab.bat"
    Delete "$INSTDIR\orcalab_logo.ico"
    Delete "$INSTDIR\uninst.exe"
    RMDir "$INSTDIR"

    Delete "$DESKTOP\OrcaLab.lnk"
    RMDir /r "$SMPROGRAMS\OrcaLab"

    DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
SectionEnd

; OrcaLab Windows Installer
; Built with NSIS (makensis), compatible with Linux CI

Unicode true
SetCompressor /SOLID lzma

!ifndef PRODUCT_VERSION
!define PRODUCT_VERSION "26.4.3"
!endif
!ifndef VI_PRODUCT_VERSION
!define VI_PRODUCT_VERSION "${PRODUCT_VERSION}.0"
!endif
!ifndef INSTALLER_SUFFIX
!define INSTALLER_SUFFIX ""
!endif
!ifndef INSTALLER_SOURCE_DIR
!define INSTALLER_SOURCE_DIR "."
!endif

!ifdef ORCALAB_ENGLISH
!include "strings_en.nsh"
!else
!include "strings_zh.nsh"
!endif

!define PRODUCT_NAME "OrcaLab"
!define PRODUCT_PUBLISHER "${STR_PRODUCT_PUBLISHER}"
!define PRODUCT_WEB_SITE "https://orca3d.cn"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\orcalab.bat"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define APP_USER_MODEL_ID "OrcaLab.Songying.OrcaLab"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\..\dist\OrcaLab-${PRODUCT_VERSION}-Setup${INSTALLER_SUFFIX}.exe"
InstallDir "$LOCALAPPDATA\OrcaLab"
InstallDirRegKey HKCU "${PRODUCT_DIR_REGKEY}" ""
RequestExecutionLevel user

VIProductVersion "${VI_PRODUCT_VERSION}"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "LegalCopyright" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "${STR_FILE_DESCRIPTION}"
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

!ifdef ORCALAB_ENGLISH
!insertmacro MUI_LANGUAGE "English"
!else
!insertmacro MUI_LANGUAGE "SimpChinese"
!endif

; ── Detect existing installation ─────────────────────────
Function .onInit
    ReadRegStr $0 HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion"
    IfErrors no_previous_version

    MessageBox MB_YESNO|MB_ICONQUESTION \
        "${STR_UPGRADE_PROMPT}" \
        IDYES upgrade_confirm
    Quit

upgrade_confirm:
    ReadRegStr $1 HKCU "${PRODUCT_UNINST_KEY}" "UninstallString"
    IfErrors skip_old_shortcut_cleanup

    ReadRegStr $2 HKCU "${PRODUCT_DIR_REGKEY}" ""
    IfErrors skip_old_shortcut_cleanup

    Delete "$DESKTOP\OrcaLab.lnk"
    RMDir /r "$SMPROGRAMS\OrcaLab"

skip_old_shortcut_cleanup:
    DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"

no_previous_version:
FunctionEnd

; ── Helper: set AppUserModelID on .lnk shortcut ───────────
Function SetShortcutAppId
    ; Stack: shortcut_path
    Pop $0
    ; Build PKEY_AppUserModel_ID: {9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3},5
    System::Call '*(g "{9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3}", i 5) p.r1'
    ; Build PROPVARIANT: VT_LPWSTR=31, pwszVal=pointer to app id string
    System::Call '*(&w "${APP_USER_MODEL_ID}") p.r2'
    System::Call '*(i 31, p r2) p.r3'
    System::Call 'ole32::CoInitialize(p 0)'
    System::Call 'shell32::SHGetPropertyStoreFromParsingName(w r0, p 0, i 2, g "{886d8eeb-8cf2-4446-8d02-cdba1dbdcf46}", *p .r4)'
    System::Call '*$4->IPropertyStore::SetValue(p r1, p r3)'
    System::Call '*$4->IPropertyStore::Commit()'
    System::Call '*$4->IUnknown::Release()'
    System::Call 'ole32::CoUninitialize()'
    System::Free $3
    System::Free $2
    System::Free $1
FunctionEnd

; ── Install Section ─────────────────────────────────────
Section "${STR_SECTION_INSTALL}"
    SetOutPath "$INSTDIR"

    File "${INSTALLER_SOURCE_DIR}\orcalab.bat"
    File "${INSTALLER_SOURCE_DIR}\orcalab.vbs"
    File "..\..\orcalab\assets\icons\orcalab_logo.ico"

    ; Run conda environment setup during installation
    DetailPrint "${STR_SETUP_ENV_DETAIL}"
    FileOpen $0 "$TEMP\orcalab_setup_only" w
    FileClose $0
    ExecWait '"$INSTDIR\orcalab.bat"' $1
    ${If} $1 != 0
        DetailPrint "${STR_SETUP_ENV_WARNING}"
    ${EndIf}

    ; Desktop shortcut (point to .vbs for invisible launch)
    CreateShortCut "$DESKTOP\OrcaLab.lnk" "$INSTDIR\orcalab.vbs" "" "$INSTDIR\orcalab_logo.ico"
    Push "$DESKTOP\OrcaLab.lnk"
    Call SetShortcutAppId

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\OrcaLab"
    CreateShortCut "$SMPROGRAMS\OrcaLab\OrcaLab.lnk" "$INSTDIR\orcalab.vbs" "" "$INSTDIR\orcalab_logo.ico"
    Push "$SMPROGRAMS\OrcaLab\OrcaLab.lnk"
    Call SetShortcutAppId
    CreateShortCut "$SMPROGRAMS\OrcaLab\Uninstall.lnk" "$INSTDIR\uninst.exe"

    ; Registry for Add/Remove Programs
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\orcalab_logo.ico"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1

    ; Uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

; ── Uninstall Section ───────────────────────────────────
Section "Uninstall"
    Delete "$INSTDIR\orcalab.bat"
    Delete "$INSTDIR\orcalab.vbs"
    Delete "$INSTDIR\orcalab_logo.ico"
    Delete "$INSTDIR\uninst.exe"
    RMDir "$INSTDIR"

    Delete "$DESKTOP\OrcaLab.lnk"
    RMDir /r "$SMPROGRAMS\OrcaLab"

    DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"
SectionEnd

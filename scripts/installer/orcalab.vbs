Function NormalizeLauncherLanguage(value)
    normalized = LCase(CStr(value))
    If normalized = "zh" Or normalized = "zh_cn" Then
        NormalizeLauncherLanguage = "zh_CN"
    ElseIf normalized = "en" Or normalized = "en_us" Then
        NormalizeLauncherLanguage = "en_US"
    Else
        NormalizeLauncherLanguage = ""
    End If
End Function

Function DetectSystemLanguage(shell)
    windowsUiLanguage = ""
    On Error Resume Next
    languageCommand = "powershell.exe -NoProfile -NonInteractive -Command """ & _
        "[Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName" & _
        """"
    Set languageProcess = shell.Exec(languageCommand)
    If Err.Number = 0 Then
        windowsUiLanguage = Trim(languageProcess.StdOut.ReadAll)
    End If
    Err.Clear
    On Error GoTo 0

    If LCase(windowsUiLanguage) = "zh" Then
        DetectSystemLanguage = "zh_CN"
    ElseIf windowsUiLanguage = "" And (GetLocale() And &H3FF) = 4 Then
        DetectSystemLanguage = "zh_CN"
    Else
        DetectSystemLanguage = "en_US"
    End If
End Function

Function ResolveLauncherLanguage(arguments, shell)
    language = ""
    index = 0
    Do While index < arguments.Count
        argument = CStr(arguments(index))
        If LCase(argument) = "--lang" Then
            language = ""
            If index + 1 < arguments.Count Then
                language = NormalizeLauncherLanguage(arguments(index + 1))
                index = index + 1
            End If
        ElseIf Left(LCase(argument), 7) = "--lang=" Then
            language = NormalizeLauncherLanguage(Mid(argument, 8))
        End If
        index = index + 1
    Loop

    If language = "" Then
        language = DetectSystemLanguage(shell)
    End If
    ResolveLauncherLanguage = language
End Function

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

envPath = WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.conda\envs\orcalab\python.exe"
If Not FSO.FileExists(envPath) Then
    launcherLanguage = ResolveLauncherLanguage(WScript.Arguments, WshShell)
    If launcherLanguage = "zh_CN" Then
        popupText = "OrcaLab " & ChrW(&H6B63) & ChrW(&H5728) & ChrW(&H9996) & _
            ChrW(&H6B21) & ChrW(&H914D) & ChrW(&H7F6E) & ChrW(&H8FD0) & _
            ChrW(&H884C) & ChrW(&H73AF) & ChrW(&H5883) & "..." & vbCrLf & _
            ChrW(&H5B89) & ChrW(&H88C5) & ChrW(&H4F9D) & ChrW(&H8D56) & _
            ChrW(&H53EF) & ChrW(&H80FD) & ChrW(&H9700) & ChrW(&H8981) & _
            ChrW(&H51E0) & ChrW(&H5206) & ChrW(&H949F) & ChrW(&H3002) & vbCrLf & _
            ChrW(&H914D) & ChrW(&H7F6E) & ChrW(&H7A97) & ChrW(&H53E3) & _
            ChrW(&H5C06) & ChrW(&H663E) & ChrW(&H793A) & ChrW(&H8FDB) & _
            ChrW(&H5EA6) & ChrW(&H3002)
        popupTitle = "OrcaLab " & ChrW(&H542F) & ChrW(&H52A8)
    Else
        popupText = "OrcaLab is preparing the runtime environment for the first time..." & vbCrLf & _
            "This may take a few minutes to install dependencies." & vbCrLf & _
            "A setup window will show the progress."
        popupTitle = "OrcaLab Startup"
    End If
    WshShell.Popup popupText, 5, popupTitle, 64
End If

command = """" & scriptDir & "\orcalab.bat"""
For Each argument In WScript.Arguments
    escapedArgument = Replace(argument, Chr(34), Chr(34) & Chr(34))
    command = command & " " & Chr(34) & escapedArgument & Chr(34)
Next

WshShell.Run command, 1, False

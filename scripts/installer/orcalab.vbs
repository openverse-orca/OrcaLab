Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

envPath = WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.conda\envs\orcalab\python.exe"
If Not FSO.FileExists(envPath) Then
    WshShell.Popup "OrcaLab is preparing the runtime environment for the first time..." & vbCrLf & _
                   "This may take a few minutes to install dependencies." & vbCrLf & _
                   "A setup window will show the progress.", 5, "OrcaLab Startup", 64
End If

WshShell.Run """" & scriptDir & "\orcalab.bat""", 1, False
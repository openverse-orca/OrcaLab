Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

envPath = WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.conda\envs\orcalab\python.exe"
If Not FSO.FileExists(envPath) Then
    WshShell.Popup "OrcaLab is preparing the runtime environment for the first time..." & vbCrLf & _
                   "This may take a few minutes to install dependencies." & vbCrLf & _
                   "A setup window will show the progress.", 5, "OrcaLab Startup", 64
End If

command = """" & scriptDir & "\orcalab.bat"""
For Each argument In WScript.Arguments
    escapedArgument = Replace(argument, Chr(34), Chr(34) & Chr(34))
    command = command & " " & Chr(34) & escapedArgument & Chr(34)
Next

WshShell.Run command, 1, False

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.Run """" & strDir & "\orcalab.bat""", 0, False
Set objShell = Nothing
Set objFSO = Nothing

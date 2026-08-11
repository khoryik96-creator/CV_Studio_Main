Option Explicit

Const EXPECTED_VERSION = "v24.6.320"
Const CV_PORT = 5000
Const HTTP_TIMEOUT_MS = 2500

Dim objShell, objFSO, scriptDir, checkURL, identityURL
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
checkURL = "http://localhost:5000/ping"
identityURL = "http://localhost:5000/instance-id"
objShell.CurrentDirectory = scriptDir

' Refuse launch until INSTALL has completed and finalized the receipt.
Dim receiptScript : receiptScript = scriptDir & "\INSTALL_RECEIPT.ps1"
If Not objFSO.FileExists(receiptScript) Then AuthorizationFailed
Dim receiptRc : receiptRc = objShell.Run("powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & receiptScript & """ -Mode Verify", 0, True)
If receiptRc <> 0 Then AuthorizationFailed

Sub AuthorizationFailed()
    MsgBox "CV Studio is not fully installed or authorized on this computer." & vbCrLf & _
           "Run INSTALL.bat and complete setup first.", 48, "CV Studio authorization required"
    WScript.Quit 13
End Sub

' Keep the startup diagnostic bounded to one active file plus one backup.
Dim timingLogPath : timingLogPath = scriptDir & "\startup_timing.log"
Dim bootStart : bootStart = Timer()
Sub LogTiming(label)
    On Error Resume Next
    If objFSO.FileExists(timingLogPath) Then
        Dim existing : Set existing = objFSO.GetFile(timingLogPath)
        If existing.Size >= 1048576 Then
            If objFSO.FileExists(timingLogPath & ".1") Then objFSO.DeleteFile timingLogPath & ".1", True
            objFSO.MoveFile timingLogPath, timingLogPath & ".1"
        End If
    End If
    Dim f : Set f = objFSO.OpenTextFile(timingLogPath, 8, True)
    f.WriteLine Now() & " | +" & FormatNumber(Timer() - bootStart, 2) & "s | " & label
    f.Close
    Err.Clear
    On Error GoTo 0
End Sub
LogTiming "launcher started"

' Make local OCR/Node/Poppler tools visible to the native runtime.
Dim envPath : envPath = objShell.ExpandEnvironmentStrings("%PATH%")
Dim p
p = scriptDir & "\tesseract" : If objFSO.FileExists(p & "\tesseract.exe") Then envPath = p & ";" & envPath
p = scriptDir & "\node" : If objFSO.FileExists(p & "\node.exe") Then envPath = p & ";" & envPath
p = scriptDir & "\poppler\Library\bin" : If objFSO.FileExists(p & "\pdfinfo.exe") Then envPath = p & ";" & envPath
objShell.Environment("PROCESS")("PATH") = envPath

Function NormalizePath(value)
    Dim s : s = LCase(Trim(CStr(value)))
    s = Replace(s, "/", "\")
    Do While Len(s) > 3 And Right(s,1) = "\" : s = Left(s,Len(s)-1) : Loop
    NormalizePath = s
End Function

Function HttpGet(url)
    On Error Resume Next
    Dim http : Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 1500, 1500, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS
    http.Open "GET", url, False
    http.setRequestHeader "Cache-Control", "no-cache"
    http.Send
    If Err.Number = 0 And http.Status >= 200 And http.Status < 300 Then HttpGet = CStr(http.responseText) Else HttpGet = ""
    Err.Clear
    On Error GoTo 0
End Function

Function CurrentIdentity()
    CurrentIdentity = Trim(HttpGet(identityURL))
End Function

Function IdentityMatches(value)
    IdentityMatches = False
    Dim parts : parts = Split(CStr(value), "|")
    If UBound(parts) < 2 Then Exit Function
    If CStr(parts(0)) <> EXPECTED_VERSION Then Exit Function
    If NormalizePath(parts(2)) <> NormalizePath(scriptDir) Then Exit Function
    IdentityMatches = True
End Function

Function PortInfo(mode, expectedPid)
    On Error Resume Next
    Dim helper : helper = scriptDir & "\INSTANCE_PORT.ps1"
    If Not objFSO.FileExists(helper) Then PortInfo = "unavailable" : Exit Function
    Dim cmd : cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & helper & """ -Mode " & mode & " -Root """ & scriptDir & """"
    If expectedPid > 0 Then cmd = cmd & " -ExpectedPid " & CStr(expectedPid)
    Dim ex : Set ex = objShell.Exec(cmd)
    PortInfo = Trim(ex.StdOut.ReadAll())
    If Err.Number <> 0 Then PortInfo = "unavailable"
    Err.Clear
    On Error GoTo 0
End Function

Function FieldOf(text, position)
    Dim values : values = Split(CStr(text), vbTab)
    If UBound(values) >= position Then FieldOf = values(position) Else FieldOf = ""
End Function

Function NodePackagesReady()
    On Error Resume Next
    NodePackagesReady = False
    If Not objFSO.FolderExists(scriptDir & "\node_modules") Then Exit Function
    Dim rc : rc = objShell.Run("cmd /d /c node -e ""require('adm-zip')"" >nul 2>&1", 0, True)
    If Err.Number = 0 And rc = 0 Then NodePackagesReady = True
    Err.Clear
    On Error GoTo 0
End Function

Sub ResolvePortConflict()
    Dim ident : ident = CurrentIdentity()
    If IdentityMatches(ident) Then Exit Sub

    Dim info : info = PortInfo("Inspect", 0)
    Dim state : state = FieldOf(info,0)
    Dim pidText : pidText = FieldOf(info,1)
    Dim ownerRoot : ownerRoot = FieldOf(info,2)
    Dim procName : procName = FieldOf(info,3)
    If state = "free" Or state = "" Or state = "unavailable" Then Exit Sub

    If state = "same" Then
        Dim stoppedSame : stoppedSame = PortInfo("Stop", CLng(pidText))
        WScript.Sleep 500
        Exit Sub
    End If

    If state = "other" Then
        Dim answer : answer = MsgBox("Another CV Studio package is using port 5000:" & vbCrLf & vbCrLf & _
            ownerRoot & vbCrLf & vbCrLf & "Stop that version and launch " & EXPECTED_VERSION & "?", 36, "Another CV Studio version is running")
        If answer <> 6 Then WScript.Quit 3
        Dim stopped : stopped = PortInfo("Stop", CLng(pidText))
        If FieldOf(stopped,0) <> "stopped" Then
            MsgBox "The other CV Studio process changed before it could be stopped. Try again.", 48, "CV Studio launch stopped"
            WScript.Quit 4
        End If
        WScript.Sleep 600
        Exit Sub
    End If

    MsgBox "Port 5000 is being used by another program:" & vbCrLf & _
           procName & " (PID " & pidText & ")" & vbCrLf & vbCrLf & _
           "CV Studio did not stop it. Close or reconfigure that program, then try again.", 48, "CV Studio cannot use port 5000"
    WScript.Quit 5
End Sub

Sub LaunchServer()
    On Error Resume Next
    Dim nativeExe : nativeExe = scriptDir & "\runtime\native\CVStudio.exe"
    If objFSO.FileExists(nativeExe) Then
        objShell.Run """" & nativeExe & """", 0, False
        If Err.Number = 0 Then On Error GoTo 0 : Exit Sub
        Err.Clear
    End If
    Dim appEntry : appEntry = scriptDir & "\app.py"
    If Not objFSO.FileExists(appEntry) And objFSO.FileExists(scriptDir & "\app.pyc") Then appEntry = scriptDir & "\app.pyc"
    Dim candidates, c
    candidates = Array("pythonw", _
      objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
      objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
      "C:\Python312\pythonw.exe", "C:\Python311\pythonw.exe")
    For Each c In candidates
        If c = "pythonw" Then
            If objShell.Run("cmd /c pythonw --version >nul 2>&1",0,True)=0 Then objShell.Run "pythonw """ & appEntry & """",0,False : On Error GoTo 0 : Exit Sub
        ElseIf objFSO.FileExists(c) Then
            objShell.Run """" & c & """ """ & appEntry & """",0,False : On Error GoTo 0 : Exit Sub
        End If
    Next
    objShell.Run "python """ & appEntry & """", 0, False
    On Error GoTo 0
End Sub

Sub EnsureWatchdog()
    Dim watchdogPath : watchdogPath = scriptDir & "\WATCHDOG.vbs"
    If Not objFSO.FileExists(watchdogPath) Then Exit Sub
    Dim watchdogRunning : watchdogRunning = False
    On Error Resume Next
    Dim wmi : Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    Dim procs : Set procs = wmi.ExecQuery("SELECT * FROM Win32_Process WHERE Name='wscript.exe' OR Name='cscript.exe'")
    Dim proc
    For Each proc In procs
        If InStr(1,LCase(CStr(proc.CommandLine)),LCase(watchdogPath),1)>0 Then watchdogRunning=True
    Next
    Err.Clear : On Error GoTo 0
    If Not watchdogRunning Then objShell.Run "wscript.exe """ & watchdogPath & """",0,False
End Sub

Dim existingIdentity : existingIdentity = CurrentIdentity()
If IdentityMatches(existingIdentity) Then
    LogTiming "exact package already running"
    EnsureWatchdog
    objShell.Run "cmd /c start """" http://localhost:5000", 0, False
    WScript.Quit 0
End If

ResolvePortConflict

' Node is the only mandatory external runtime for protected DOCX export.
If Not NodePackagesReady() Then
    LogTiming "adm-zip missing or damaged; refusing launch-time network install"
    MsgBox "The required Node package adm-zip is missing or damaged. Run INSTALL.bat and complete setup again.",48,"CV Studio installation incomplete"
    WScript.Quit 6
End If

LaunchServer
Dim waitedMs : waitedMs = 0
Dim liveIdentity : liveIdentity = ""
Do While waitedMs < 60000
    WScript.Sleep 250
    waitedMs = waitedMs + 250
    liveIdentity = CurrentIdentity()
    If IdentityMatches(liveIdentity) Then Exit Do
    If liveIdentity <> "" And Not IdentityMatches(liveIdentity) Then Exit Do
Loop
LogTiming "startup wait ms=" & waitedMs

If Not IdentityMatches(liveIdentity) Then
    Dim runtimeLog : runtimeLog = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\TheGuoLab\CVStudio\runtime.log"
    MsgBox "CV Studio did not start as the expected package." & vbCrLf & vbCrLf & _
           "Expected: " & EXPECTED_VERSION & vbCrLf & _
           "Response: " & liveIdentity & vbCrLf & vbCrLf & _
           "Check: " & runtimeLog, 48, "CV Studio startup failed"
    WScript.Quit 7
End If

objShell.Run "cmd /c start """" http://localhost:5000", 0, False

' Start only this exact package's watchdog.
EnsureWatchdog
LogTiming "launcher finished"

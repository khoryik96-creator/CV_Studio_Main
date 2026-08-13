Option Explicit
Const EXPECTED_VERSION = "v24.6.327"
Const HTTP_TIMEOUT_MS = 2500
Dim objShell,objFSO,scriptDir,identityURL,missed
Set objShell=CreateObject("WScript.Shell")
Set objFSO=CreateObject("Scripting.FileSystemObject")
scriptDir=objFSO.GetParentFolderName(WScript.ScriptFullName)
identityURL="http://localhost:5000/instance-id"
objShell.CurrentDirectory=scriptDir
missed=0

Function NormalizePath(value)
  Dim s:s=LCase(Trim(CStr(value))):s=Replace(s,"/","\")
  Do While Len(s)>3 And Right(s,1)="\":s=Left(s,Len(s)-1):Loop
  NormalizePath=s
End Function
Function HttpGet(url)
  On Error Resume Next
  Dim h:Set h=CreateObject("MSXML2.ServerXMLHTTP.6.0")
  h.setTimeouts 1500,1500,HTTP_TIMEOUT_MS,HTTP_TIMEOUT_MS
  h.Open "GET",url,False:h.setRequestHeader "Cache-Control","no-cache":h.Send
  If Err.Number=0 And h.Status>=200 And h.Status<300 Then HttpGet=CStr(h.responseText) Else HttpGet=""
  Err.Clear:On Error GoTo 0
End Function
Function SameIdentity(value)
  SameIdentity=False
  Dim p:p=Split(CStr(value),"|")
  If UBound(p)>=2 Then If p(0)=EXPECTED_VERSION And NormalizePath(p(2))=NormalizePath(scriptDir) Then SameIdentity=True
End Function
Function PortInfo(mode,pid)
  On Error Resume Next
  Dim cmd:cmd="powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & scriptDir & "\INSTANCE_PORT.ps1"" -Mode " & mode & " -Root """ & scriptDir & """"
  If pid>0 Then cmd=cmd & " -ExpectedPid " & CStr(pid)
  Dim ex:Set ex=objShell.Exec(cmd):PortInfo=Trim(ex.StdOut.ReadAll())
  If Err.Number<>0 Then PortInfo="unavailable"
  Err.Clear:On Error GoTo 0
End Function
Function F(text,n)
  Dim a:a=Split(CStr(text),vbTab):If UBound(a)>=n Then F=a(n) Else F=""
End Function
Function NodePackagesReady()
  On Error Resume Next
  NodePackagesReady=False
  If Not objFSO.FolderExists(scriptDir & "\node_modules") Then Exit Function
  Dim rc:rc=objShell.Run("cmd /d /c node -e ""require('adm-zip')"" >nul 2>&1",0,True)
  If Err.Number=0 And rc=0 Then NodePackagesReady=True
  Err.Clear:On Error GoTo 0
End Function
Sub LaunchServer()
  On Error Resume Next
  If Not NodePackagesReady() Then Exit Sub
  Dim native:native=scriptDir & "\runtime\native\CVStudio.exe"
  If objFSO.FileExists(native) Then objShell.Run """" & native & """",0,False:On Error GoTo 0:Exit Sub
  Dim entry:entry=scriptDir & "\app.py":If Not objFSO.FileExists(entry) And objFSO.FileExists(scriptDir & "\app.pyc") Then entry=scriptDir & "\app.pyc"
  objShell.Run "pythonw """ & entry & """",0,False
  On Error GoTo 0
End Sub

Do
  WScript.Sleep 15000
  Dim ident:ident=Trim(HttpGet(identityURL))
  If SameIdentity(ident) Then
    missed=0
  ElseIf ident<>"" Then
    ' Another package now owns the port. This watchdog must never revive the old one.
    WScript.Quit 0
  Else
    missed=missed+1
    If missed>=2 Then
      missed=0
      Dim info:info=PortInfo("Inspect",0)
      Dim state:state=F(info,0)
      If state="same" Then
        Dim stopResult : stopResult = PortInfo("Stop",CLng(F(info,1)))
        WScript.Sleep 600
        LaunchServer
      ElseIf state="free" Then
        LaunchServer
      Else
        ' Other CV Studio or an unrelated service owns port 5000.
        WScript.Quit 0
      End If
      WScript.Sleep 8000
    End If
  End If
Loop

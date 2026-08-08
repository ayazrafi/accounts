; Script generated automatically by build_installer.py
[Setup]
AppId={{5E21F459-22B2-4E57-9A10-449C1AD334B5}}
AppName=Bestie Accounts
AppVersion=1.0.0
DefaultDirName={autopf}\BestieAccounts
DefaultGroupName=Bestie Accounts
OutputDir=dist\installer
OutputBaseFilename=BestieAccountsSetup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
CloseApplicationsFilter=*BestieAccounts.exe,*mongod.exe

[InstallDelete]
; Clean up the old _internal folder completely to remove old/unnecessary libraries on direct upgrade
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Copy all compiled Python app files from PyInstaller output
Source: "dist\BestieAccounts\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

; Copy local MongoDB binary to the app's bin folder
Source: "bin\mongod.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Icons]
Name: "{group}\Bestie Accounts"; Filename: "{app}\BestieAccounts.exe"
Name: "{autodesktop}\Bestie Accounts"; Filename: "{app}\BestieAccounts.exe"

[Run]
Description: "Launch Bestie Accounts"; Flags: postinstall nowait skipifsilent; Filename: "{app}\BestieAccounts.exe"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Force close any running instances of the app and database before starting installation
  Exec('taskkill', '/f /im BestieAccounts.exe /t', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill', '/f /im mongod.exe /t', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

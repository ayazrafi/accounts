; Script generated automatically by build_installer.py
[Setup]
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

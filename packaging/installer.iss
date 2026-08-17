#ifndef AppVersion
  #error AppVersion must be defined, for example: /DAppVersion=0.1.0
#endif

[Setup]
; Never change AppId: Inno Setup uses it to match upgrades to existing installs.
AppId={{E5758097-D0C7-4CE5-89C2-66812117AB43}
AppName=StoneReader
AppPublisher=Andrew Johnson
AppVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\StoneReader
DefaultGroupName=StoneReader
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\StoneReader.exe
OutputDir=..\dist
OutputBaseFilename=StoneReader-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
WizardStyle=modern

[Files]
Source: "..\dist\StoneReader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\StoneReader"; Filename: "{app}\StoneReader.exe"

[Run]
Filename: "{app}\StoneReader.exe"; Description: "Launch StoneReader"; Flags: nowait postinstall skipifsilent
; A silent updater run must relaunch the app after replacing it.
Filename: "{app}\StoneReader.exe"; Flags: nowait; Check: WizardSilent

; Instalador do Clack para Windows (Inno Setup 6).
; Compilar a partir da raiz do repositório, depois do PyInstaller:
;   ISCC.exe /DAppVersion=1.0.0 desktop\windows-installer.iss
; Instala só para o usuário atual (sem pedir administrador).

#ifndef AppVersion
  #error Passe a versão: ISCC /DAppVersion=x.y.z
#endif

[Setup]
AppId={{8C1F3F5E-6C2B-4C51-9B7E-3D3A8E1C1A11}
AppName=Clack
AppVersion={#AppVersion}
AppPublisher=Renan Leitão
AppPublisherURL=https://github.com/Lobbyboya/clack
AppSupportURL=https://github.com/Lobbyboya/clack/issues
DefaultDirName={autopf}\Clack
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Clack-{#AppVersion}-windows-x64-setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Clack.exe
UninstallDisplayName=Clack
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Clack\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Clack"; Filename: "{app}\Clack.exe"
Name: "{autodesktop}\Clack"; Filename: "{app}\Clack.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Clack.exe"; Description: "{cm:LaunchProgram,Clack}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Fecha o Clack (ele fica na bandeja) antes de apagar os arquivos.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Clack.exe"; Flags: runhidden; RunOnceId: "FecharClack"

[Registry]
; Se o usuário ligou "Iniciar com o sistema", a desinstalação desfaz isso.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Clack"; Flags: uninsdeletevalue dontcreatekey

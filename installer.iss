; =============================================================================
; StarVisibility — Inno Setup 6 installer script
;
; Produces:  dist\StarVisibility-Setup-1.0.0.exe
; Requires:  Inno Setup 6 — https://jrsoftware.org/isinfo.php
;            Both EXEs must be built first:
;              .\build_exe.ps1 -Clean          (builds StarVisibility.exe)
;              .\build_exe.ps1 -Console        (builds StarVisibility-Console.exe)
;            Or in one shot:
;              .\build_exe.ps1 -Installer -Clean
; =============================================================================

[Setup]
AppName=StarVisibility
AppVersion=1.0.0
AppVerName=StarVisibility 1.0.0
AppPublisher=INAF / OGS CaNaPy Team
AppPublisherURL=https://github.com/AleDiFi/StarVisibility
AppSupportURL=https://github.com/AleDiFi/StarVisibility/issues
; Default install location: auto uses Program Files on admin, AppData on user
DefaultDirName={autopf}\StarVisibility
DefaultGroupName=StarVisibility
; Output installer into dist\ so everything lands in one place
OutputDir=dist
OutputBaseFilename=StarVisibility-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 64-bit installation
ArchitecturesInstallIn64BitMode=x64compatible
; Allow both admin (Program Files) and non-admin (AppData) installs
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main GUI executable (no console window)
Source: "dist\StarVisibility.exe"; DestDir: "{app}"; Flags: ignoreversion
; Console variant — stdout visible; useful for --headless mode and pipelines
Source: "dist\StarVisibility-Console.exe"; DestDir: "{app}"; Flags: ignoreversion
; Default CaNaPy April 2026 campaign configuration
Source: "canopy_april2026_default.json"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Pre-create runtime directories so the app writes there on first launch
Name: "{app}\.cache"
Name: "{app}\logs"
Name: "{app}\output"

[Icons]
Name: "{group}\StarVisibility";                                  Filename: "{app}\StarVisibility.exe"
Name: "{group}\StarVisibility - Console (Headless)";             Filename: "{app}\StarVisibility-Console.exe"
Name: "{group}\{cm:UninstallProgram,StarVisibility}";            Filename: "{uninstallexe}"
Name: "{autodesktop}\StarVisibility";                            Filename: "{app}\StarVisibility.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StarVisibility.exe"; Description: "{cm:LaunchProgram,StarVisibility}"; Flags: nowait postinstall skipifsilent

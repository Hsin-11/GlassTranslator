#ifndef AppVersion
#define AppVersion "0.2.7"
#endif

#define AppName "Glass Translator"
#define AppPublisher "Glass Translator Project"

[Setup]
AppId={{B6F8F812-94EE-43C8-AC0E-0F322E2F279A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\GlassTranslator
DefaultGroupName=Glass Translator
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=installer_output
OutputBaseFilename=GlassTranslator_Setup_x64_v{#AppVersion}
SetupIconFile=assets\glass_translator.ico
UninstallDisplayIcon={app}\GlassTranslator.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\GlassTranslator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Glass Translator"; Filename: "{app}\GlassTranslator.exe"
Name: "{autodesktop}\Glass Translator"; Filename: "{app}\GlassTranslator.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GlassTranslator.exe"; Description: "Launch Glass Translator"; Flags: postinstall nowait skipifsilent

; Instalador de BPM auToe (Inno Setup 6). Lo arma publicar_version.py; a mano:
;   ISCC.exe /DVersion=0.7.0 bpm_autoe.iss
; Se instala solo para el usuario (sin pedir permiso de administrador) en %LOCALAPPDATA%\Programs\BPM auToe.
; Instalar una versión nueva encima reemplaza la anterior; la configuración (%APPDATA%\BPM auToe) no se toca.

#ifndef Version
  #define Version "0.0.0"
#endif
#define Nombre "BPM auToe"
#define Exe "BPM auToe.exe"

[Setup]
AppId={{1B104F2E-FE93-4FEF-922D-5C5E344E4327}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=Toe
AppPublisherURL=https://github.com/full-toe/BPM-auToe
AppSupportURL=https://github.com/full-toe/BPM-auToe/issues
AppUpdatesURL=https://github.com/full-toe/BPM-auToe/releases
DefaultDirName={localappdata}\Programs\{#Nombre}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=salida
OutputBaseFilename=BPM-auToe-{#Version}-instalador
SetupIconFile=..\app\bpm_autoe.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
LicenseFile=..\LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#Version}
VersionInfoProductName={#Nombre}
VersionInfoDescription=Instalador de {#Nombre}

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso en el escritorio"; Flags: unchecked

[Files]
Source: "salida\{#Exe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\{#Nombre}"; Filename: "{app}\{#Exe}"; AppUserModelID: "Toe.BPMAUTOE"; Comment: "Detector de BPM (OSC, Ableton Link)"
Name: "{userdesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; AppUserModelID: "Toe.BPMAUTOE"; Tasks: escritorio

[Run]
; También corre en las actualizaciones silenciosas: la app se vuelve a abrir sola.
; Se abre con PYINSTALLER_RESET_ENVIRONMENT=1 porque la app que lanzó la actualización (0.7.0) le pasa al
; instalador sus variables de PyInstaller; sin esto la app nueva falla con «Failed to load Python DLL».
Filename: "{cmd}"; Parameters: "/c set PYINSTALLER_RESET_ENVIRONMENT=1&& start """" ""{app}\{#Exe}"""; Description: "Abrir {#Nombre}"; Flags: nowait postinstall runhidden

import os
import sys
import subprocess
import shutil

def main():
    print("==================================================")
    print(" Bestie Accounts - Build Automation Script (Option B)")
    print("==================================================")

    # 1. Run PyInstaller
    print("\n Step 1: Running PyInstaller...")
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=BestieAccounts",
        "--add-data=.env;.",  # Include .env template
        "--add-data=frontend/images;frontend/images",  # Include GUI images
        "--add-data=frontend/assets;frontend/assets",  # Include theme assets and icons
        "--hidden-import=openpyxl",  # Force include openpyxl for Excel export
        "--hidden-import=pandas",    # Force include pandas for importing vouchers
        "main.py"
    ]
    
    print(f"Executing: {' '.join(pyinstaller_cmd)}")
    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("[SUCCESS] PyInstaller build completed successfully!")
    except FileNotFoundError:
        print("[ERROR] 'pyinstaller' is not installed or not in PATH.")
        print("Please run: pip install pyinstaller")
        return
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PyInstaller failed with exit code {e.returncode}")
        return

    # 2. Check for mongod.exe
    print("\n Step 2: Checking for mongod.exe...")
    project_bin_dir = os.path.join(os.getcwd(), "bin")
    mongod_path = os.path.join(project_bin_dir, "mongod.exe")
    
    if not os.path.isfile(mongod_path):
        os.makedirs(project_bin_dir, exist_ok=True)
        print("[WARNING] 'bin/mongod.exe' not found in your project folder.")
        print("To package MongoDB successfully, please:")
        print(f"  1. Download MongoDB Community Server ZIP for Windows.")
        print(f"  2. Copy 'mongod.exe' into this folder: {project_bin_dir}")
        print("You can still compile Inno Setup later once you place mongod.exe in that directory.")
    else:
        print("[SUCCESS] Found mongod.exe in bin/ folder.")

    # 3. Generate Inno Setup Script
    print("\n Step 3: Generating 'setup.iss' script for Inno Setup...")
    iss_content = f"""; Script generated automatically by build_installer.py
[Setup]
AppName=Bestie Accounts
AppVersion=1.0.0
DefaultDirName={{autopf}}\\BestieAccounts
DefaultGroupName=Bestie Accounts
OutputDir=dist\\installer
OutputBaseFilename=BestieAccountsSetup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Files]
; Copy all compiled Python app files from PyInstaller output
Source: "dist\\BestieAccounts\\*"; DestDir: "{{app}}"; Flags: recursesubdirs createallsubdirs

; Copy local MongoDB binary to the app's bin folder
Source: "bin\\mongod.exe"; DestDir: "{{app}}\\bin"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\Bestie Accounts"; Filename: "{{app}}\\BestieAccounts.exe"
Name: "{{autodesktop}}\\Bestie Accounts"; Filename: "{{app}}\\BestieAccounts.exe"

[Run]
Description: "Launch Bestie Accounts"; Flags: postinstall nowait skipifsilent; Filename: "{{app}}\\BestieAccounts.exe"
"""
    
    iss_path = os.path.join(os.getcwd(), "setup.iss")
    with open(iss_path, "w", encoding="utf-8") as f:
        f.write(iss_content)
        
    print(f"[SUCCESS] Generated setup.iss: {iss_path}")

    print("\n==================================================")
    print(" All steps complete! Ready to compile the installer.")
    print("==================================================")
    print("To compile your professional Setup Installer:")
    print("  1. Ensure you have 'bin/mongod.exe' in your project root.")
    print("  2. Open Inno Setup (Compiler).")
    print(f"  3. Open 'setup.iss' ({iss_path})")
    print("  4. Press Ctrl+F9 (or click Build > Compile) in Inno Setup.")
    print("  5. Your distributed installer will be saved at: dist\\installer\\BestieAccountsSetup.exe")
    print("==================================================")

if __name__ == "__main__":
    main()

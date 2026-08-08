import os
import sys
import shutil
from dotenv import load_dotenv

def get_env_path() -> str:
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        config_dir = os.path.join(appdata, "BestieAccounts")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, ".env")
    else:
        return os.path.abspath(".env")

def load_env():
    env_path = get_env_path()
    if getattr(sys, 'frozen', False):
        # In frozen production mode, check if we have a user-writable .env file in Local AppData.
        # If not, try to copy the template from the bundled folder.
        if not os.path.exists(env_path):
            copied = False
            # Check next to executable (onedir mode)
            exe_dir = os.path.dirname(sys.executable)
            bundled_env = os.path.join(exe_dir, ".env")
            if os.path.exists(bundled_env):
                try:
                    shutil.copy2(bundled_env, env_path)
                    copied = True
                except Exception as e:
                    print(f"Error copying bundled .env template: {e}")
            
            # Check sys._MEIPASS if not copied (onefile mode or fallback)
            if not copied:
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    bundled_env_meipass = os.path.join(meipass, ".env")
                    if os.path.exists(bundled_env_meipass):
                        try:
                            shutil.copy2(bundled_env_meipass, env_path)
                            copied = True
                        except Exception as e:
                            print(f"Error copying bundled .env from MEIPASS: {e}")
            
            # Ensure file exists
            if not os.path.exists(env_path):
                try:
                    with open(env_path, "w") as f:
                        f.write("")
                except Exception as e:
                    print(f"Error creating empty .env file: {e}")
    load_dotenv(env_path)

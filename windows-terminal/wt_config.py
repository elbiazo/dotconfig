from pathlib import Path, WindowsPath
import glob
import json
import os
def get_localappdata() -> WindowsPath:
    return WindowsPath.home().joinpath('AppData', 'Local')


def set_wt_action(wt_setting_path:WindowsPath, action_conf_path: WindowsPath) -> dict:
    if wt_setting_path.exists() and action_conf_path.exists():
        with open(wt_setting_path, 'r+') as setting_fd:
            with open(action_conf_path, 'r') as action_fd:
                settings = json.load(setting_fd)
                new_actions = json.load(action_fd)

                # Get all the actions related to command
                new_keys_cmd = {}
                for command in new_actions['actions']:
                    keys = command.get('keys')
                    if keys:
                        new_keys_cmd[command['keys']] = command
                    else:
                        print("From New Config: No keys or direction found for command. Likely bad config: ", command)


                # Update the settings with the new actions. if key isn't found,
                # add it to the settings. If it is found, update the action
                updated_actions = []
                for command in settings['actions']:
                    keys = command.get('keys')
                    if keys:
                        if keys in new_keys_cmd:
                            updated_actions.append(new_keys_cmd[keys])
                        else:
                            print("Key not found in new actions Might want to delete that in current setting or add it to wt_action.json: ", keys)
                    else:
                        print("From WT Settings: No keys or direction found for command. Likely bad config: ", command)

                settings['actions'] = updated_actions

                # Write the updated settings back to the file
                setting_fd.seek(0)
                setting_fd.write(json.dumps(settings, indent=4))
                setting_fd.truncate()

    else:
        print("Settings file not found")
        exit(-1)

    return settings

def main():
    script_path = os.path.dirname(os.path.realpath(__file__))
    packages_dir = get_localappdata()/"Packages"
    if packages_dir.exists():
        terminal_settings = glob.glob(str(packages_dir) + "/*Terminal*/LocalState/settings.json")

        if len(terminal_settings) > 0:
            wt_setting_path = WindowsPath(terminal_settings[0])
            set_wt_action(wt_setting_path, WindowsPath(script_path + "/wt_action.json"))

            # TODO: need to do this for wt_config as well
    else:
        print("Packages directory not found")
        return

if __name__ == '__main__':
    main()


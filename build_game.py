import os
import shutil
import sys
import subprocess


class BuildData:
    def __init__(self):
        self.Changelist = ""
        self.Source = ""
        self.Game = ""
        self.ClientConfig = ""
        self.ProjectName = "S1Game"
        self.GameConfig = ""


class BuildSystem:
    def __init__(self, *args):
        self.build_data = BuildData()
        self.source_binaries = os.path.join(self.build_data.Source, self.build_data.ProjectName, "Binaries", "Win64")
        self.game_path = ""
        self.game_binaries = ""

    def build_exe(self):

        UAT_Path = os.path.join(self.build_data.Source, "UE5EA", "Engine", "Build", "BatchFiles", "RunUAT.bat")
        CMD_Params = "BuildCookRun -project={0}/{1}/{1}.uproject -platform=Win64 -target={1} -clientconfig={2}".format(
            self.build_data.Source, self.build_data.ProjectName, self.build_data.ClientConfig)

        CMD_Params += " -noP4 -stdout -UTF8Output -Build -SkipCook -SkipStage -SkipPackage -skipbuildeditor -nobootstrapexe"

        subprocess.run("{0} {1}".format(UAT_Path, CMD_Params), shell=True, stdout=None, encoding="UTF8")

    def find_game(self):
        match_name = "_{0}_{1}_Win64".format(self.build_data.Changelist, self.build_data.GameConfig)

        result = []
        for d in os.listdir(self.build_data.Game):
            path = os.path.join(self.build_data.Game, d)
            if not os.path.isdir(path): continue
            if match_name in d and d.startswith("S1Game"):
                result.append(os.path.join(self.build_data.Game, d))

        if len(result) == 1:
            self.game_path = result[0]
            self.game_binaries = os.path.join(self.game_path, "Win64", self.build_data.ProjectName, "Binaries", "Win64")
        else:
            print("No game found")

    def exists(self):
        if len(self.game_path) == 0:
            print(self.game_path)
            return False
        if not os.path.exists(self.game_path):
            print(self.game_path)
            return False

        for ext in ['.exe', '.pdb']:
            src_path = os.path.join(self.source_binaries, self.make_game_name() + ext)
            if not os.path.exists(src_path):
                print(src_path + " not found")
                return False
        return True

    def make_game_name(self):
        return self.build_data.ProjectName

    def copy_file(self,ext):
        src_path = os.path.join(self.source_binaries, self.make_game_name() + ext)
        tar_path = os.path.join(self.game_binaries, self.make_game_name() + ext)
        shutil.copy(src_path, tar_path)


    def replace_exe(self):

        self.copy_file('.exe')
        self.copy_file('.pdb')

        print("start " + os.path.join(self.game_binaries, self.make_game_name() + ".exe"))

    def remove_old_build(self):
        for ext in [".exe", ".pdb"]:
            src_path = os.path.join(self.source_binaries, self.make_game_name() + ext)
            if os.path.exists(src_path):
                os.remove(src_path)

    def start_process(self):
        # waitforattach
        game_exe = os.path.join(self.build_data.Game, "Win64", "ProjectN.exe")
        cmd = [game_exe]
        cmd = cmd.extend(self.process_args)
        subprocess.Popen(cmd)

    def run(self):
        self.remove_old_build()
        self.build_exe()
        self.find_game()
        if self.exists():
            self.replace_exe()
        else:
            print("file not exists")


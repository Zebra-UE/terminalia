import shutil
import threading
import tkinter as tk
import subprocess
import os
import tkinter.filedialog
from datetime import time
from threading import Thread
from time import sleep
from tkinter import ttk


class BuildSetting:
    def __init__(self):
        self.P4PORT = ""
        self.P4USER = ""
        self.P4CLIENT = ""


class SettingSaver:
    def __init__(self):
        pass

    def save(self, build_setting: BuildSetting):
        value = "{0}\n{1}\n{2}\n".format(build_setting.P4PORT, build_setting.P4USER, build_setting.P4CLIENT)
        with open('settings.ini', 'w', encoding='UTF8') as f:
            f.write(value)

    def load(self):
        build_setting: BuildSetting = BuildSetting()
        if os.path.exists('settings.ini'):
            with open('settings.ini', 'r', encoding='UTF8') as f:
                lines = f.readlines()
                build_setting.P4PORT = lines[0].strip(" \n")
                build_setting.P4USER = lines[1].strip(" \n")
                build_setting.P4CLIENT = lines[2].strip(" \n")
        return build_setting


class BuildData:
    def __init__(self):
        self.ClientRoot = ""
        self.ProjectRelativePath = "S1Game"
        self.EngineRelativePath = "UE5EA"

        self.ProjectName = ""

        self.ClientStream = ""
        self.ChangeList = ""
        self.GameConfig = ""
        self.TargetPath = "D:/Game/"

        self.sync = False
        self.build_editor = False
        self.build_game = False
        self.replace_target: bool | str = False
        self.start_game: bool = False
        self.step = 0
        self.progress_value = 0


class ViewData:
    def __init__(self):
        self.step = 0
        self.progress_value = 0


class ListView:
    class Node:
        def __init__(self, view, width):
            self.view = view
            self.width = width

    def __init__(self, span=2):
        self.span = span
        self.children = []

    def add_child(self, view, width=0):
        self.children.append(ListView.Node(view, width))

    def place(self, **kwargs):
        x = kwargs['x']
        y = kwargs['y']
        w = 0
        for i in range(len(self.children)):
            node = self.children[i]
            if i == 0:
                node.view.place(x=x, y=y, width=node.width)
                w = node.width
            else:
                node.view.place(x=x + w + i * self.span, y=y, width=node.width)
                w += node.width

    def place_forget(self):
        for i in range(len(self.children)):
            self.children[i].view.place_forget()


class TreeView:
    class TreeNode:
        def __init__(self):
            self.view = None
            self.visibility: bool = False
            self.parent: int = -1
            self.children: [int] = []

    def __init__(self):
        self.tree_node = []
        self.base_x = 0
        self.base_y = 0
        self.node_height = 30

    def add_child(self, view, parent=-1):
        node = TreeView.TreeNode()
        node.view = view
        # view.place_forget()
        node.visibility = parent < 0
        node.parent = parent
        id = len(self.tree_node)
        if parent >= 0:
            self.tree_node[parent].children.append(id)
        self.tree_node.append(node)
        return id

    def update(self):
        x = 0
        y = self.base_y
        num = 0
        for i in range(0, len(self.tree_node)):
            node = self.tree_node[i]
            if node.parent >= 0:
                x = 26
            else:
                x = 0
            if node.visibility:
                node.view.place(x=x + self.base_x, y=y + self.node_height * num)
                num += 1
            else:
                node.view.place_forget()

    def expand(self, i):
        self.toggle(i, True)

    def collect(self, i):
        self.toggle(i, False)

    def toggle(self, i, v):
        for node in self.tree_node:
            if node.parent == i:
                node.visibility = v
        self.update()


class MainView(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)

        self.build_setting = BuildSetting()
        self.build_data = BuildData()
        self.view_data = ViewData()
        self.tk_P4PORT = tk.StringVar()
        self.tk_P4USER = tk.StringVar()
        self.tk_P4CLIENT = tk.StringVar()
        self.tk_sync = tk.IntVar()
        self.tk_build_editor = tk.IntVar()
        self.tk_build_exe = tk.IntVar()
        self.tk_replace = tk.IntVar()
        self.tk_change_list = tk.StringVar()
        self.progress_bar = None
        self.progress_text = tk.StringVar()
        self.tk_game_config_combobox = None
        self.left_tree = None

        self.build_system = None

        self.geometry("700x500")
        self.read_default()
        self.create_view()

    def read_default(self):
        setting_saver_file = SettingSaver()
        setting_saver = setting_saver_file.load()
        self.tk_P4PORT.set(setting_saver.P4PORT)
        self.tk_P4USER.set(setting_saver.P4USER)
        self.tk_P4CLIENT.set(setting_saver.P4CLIENT)
        self.build_setting.P4PORT = setting_saver.P4PORT
        self.build_setting.P4USER = setting_saver.P4USER
        self.build_setting.P4CLIENT = setting_saver.P4CLIENT

    def create_view(self):
        frame_background_color = "darkgrey"
        frame_forward_color = "black"
        frame = tk.Frame(self, bg=frame_background_color)
        frame.place(x=0, y=0, width=700, height=60)

        tk.Label(frame, text='Server', font=('Arial', 10), bg=frame_background_color, fg=frame_forward_color).place(x=0,
                                                                                                                    y=5)
        tk.Entry(frame, font=('Arial', 10), textvariable=self.tk_P4PORT).place(x=2, y=25, width=200)

        tk.Label(frame, text='User', font=('Arial', 10), bg=frame_background_color, fg=frame_forward_color).place(x=204,
                                                                                                                  y=5)
        tk.Entry(frame, font=('Arial', 10), textvariable=self.tk_P4USER).place(x=204, y=25, width=200)

        tk.Label(frame, text='Workspace', font=('Arial', 10), bg=frame_background_color, fg=frame_forward_color).place(
            x=406, y=5)
        tk.Entry(frame, font=('Arial', 10), textvariable=self.tk_P4CLIENT).place(x=406, y=25, width=200)

        row_bg = "whitesmoke"
        left_frame = tk.Frame(self, bg=row_bg)
        left_frame.place(x=0, y=60, width=220, height=440)

        self.left_tree = TreeView()

        i = self.left_tree.add_child(tk.Checkbutton(left_frame, text="1. sync", variable=self.tk_sync, bg=row_bg,
                                                    command=lambda: self.switch_sync_checkbox()), -1)
        h = ListView()
        h.add_child(tk.Label(left_frame, text='change:', bg=row_bg), width=56)
        h.add_child(tk.Entry(left_frame, textvariable=self.tk_change_list), width=120)
        self.left_tree.add_child(h, i)

        self.left_tree.add_child(
            tk.Checkbutton(left_frame, text="2. build editor", variable=self.tk_build_editor, bg=row_bg))
        i = self.left_tree.add_child(
            tk.Checkbutton(left_frame, text="3. build game", variable=self.tk_build_exe, bg=row_bg,
                           command=lambda: self.switch_build_game_checkbox()))

        h = ListView()
        h.add_child(tk.Label(left_frame, text='config:', bg=row_bg), width=56)

        game_config = ["Development", "Test", "Shipping"]
        self.tk_game_config_combobox = ttk.Combobox(left_frame, values=game_config, font=('Arial', 12))
        self.tk_game_config_combobox.current(1)
        h.add_child(self.tk_game_config_combobox, width=120)
        self.left_tree.add_child(h, parent=i)

        self.left_tree.add_child(
            tk.Checkbutton(left_frame, text="4. replace...", variable=self.tk_replace, bg=row_bg))

        self.left_tree.add_child(tk.Checkbutton(left_frame, text="5. start game,with cmd:", bg=row_bg))

        self.left_tree.update()

        b = tk.Button(left_frame, text='Build', font=('Arial', 10), width=10, height=1,
                      command=lambda: self.run())
        b.place(x=10, y=400)

        right_frame = tk.Frame(self, bg="beige")
        right_frame.place(x=220, y=60, width=480, height=440)
        list_view = tk.Listbox(right_frame, bg="beige")
        list_view.place(x=0, y=0, height=380, width=480)

        self.progress_text.set("waiting...")
        c = tk.Label(right_frame, textvariable=self.progress_text, font=('Arial', 8))
        c.place(x=20, y=380)
        self.progress_bar = ttk.Progressbar(right_frame)
        self.progress_bar.place(x=10, y=420, width=460, height=6)

        self.schedule_tick()
        self.mainloop()

    def switch_sync_checkbox(self):
        if self.tk_sync.get():
            self.left_tree.expand(0)
        else:
            self.left_tree.collect(0)

    def switch_build_game_checkbox(self):
        if self.tk_build_exe.get():
            self.left_tree.expand(3)
        else:
            self.left_tree.collect(3)

    def schedule_tick(self):
        self.tick()
        self.after(100, lambda: self.schedule_tick())

    def tick(self):
        if self.view_data.step != self.build_data.step:
            self.view_data.step = self.build_data.step
            if self.view_data.step == 1:
                self.progress_text.set("sync...")
            elif self.view_data.step == 2:
                self.progress_text.set("build editor")
            elif self.view_data.step == 3:
                self.progress_text.set("build game")

            elif self.view_data.step == -1:
                self.build_system = None

            self.progress_bar.step(0 - self.view_data.progress_value)
            self.view_data.progress_value = 0

        if self.view_data.step == 1:
            progress_step_value = self.build_data.progress_value - self.view_data.progress_value
            if progress_step_value > 0:
                self.progress_bar.step(progress_step_value)
                self.view_data.progress_value = self.build_data.progress_value

        self.update()

    def step(self):
        self.build_data.ChangeList = self.tk_change_list.get()
        self.build_data.sync = self.tk_sync.get()
        self.build_data.build_editor = self.tk_build_editor.get()
        self.build_data.build_game = self.tk_build_exe.get()
        self.build_data.GameConfig = self.tk_game_config_combobox.get()

        #
        project_path = os.path.join(self.build_data.ClientRoot, self.build_data.ProjectRelativePath)
        for f in os.listdir(project_path):
            if f.endswith(".uproject"):
                self.build_data.ProjectName = f[:-9]

        self.build_data.replace_target = self.tk_replace.get()

    def run(self):
        if self.build_system is not None:
            return

        self.view_data.step = -1
        self.save_setting()
        self.step()
        self.init_p4()

        self.build_system = BuildSystem(self.build_data)
        self.build_system.daemon = True
        self.build_system.start()

    def save_setting(self):
        self.build_setting.P4PORT = self.tk_P4PORT.get()
        self.build_setting.P4USER = self.tk_P4USER.get()
        self.build_setting.P4CLIENT = self.tk_P4CLIENT.get()

        setting_saver_file = SettingSaver()
        setting_saver_file.save(self.build_setting)

    def init_p4(self):
        subprocess.check_output('p4 set P4PORT={0}'.format(self.build_setting.P4PORT))
        subprocess.check_output('p4 set P4USER={0}'.format(self.build_setting.P4USER))
        subprocess.check_output('p4 set P4CLIENT={0}'.format(self.build_setting.P4CLIENT))

        output = subprocess.check_output('p4 info', encoding='utf-8')
        output = output.strip()
        output = output.split("\n")
        for line in output:
            line = line.strip()
            if line.startswith("Client root:"):
                self.build_data.ClientRoot = line[len("Client root:") + 1:].strip()
            elif line.startswith("Client stream:"):
                self.build_data.ClientStream = line[len("Client stream:") + 1:].strip()


class BuildSystem(threading.Thread):
    def __init__(self, build_data: BuildData):
        threading.Thread.__init__(self)
        self.build_data = build_data
        self.need_sync_source_files: [str] = []

    def run(self):
        self.build_data.step = 0

        sync_content_process = None
        if self.build_data.sync:
            self.need_sync_source_files.extend(self.get_sync_file("UE5EA/"))
            self.need_sync_source_files.extend(
                self.get_sync_file("{0}/Source/".format(self.build_data.ProjectRelativePath)))
            self.need_sync_source_files.extend(
                self.get_sync_file("{0}/Plugins/".format(self.build_data.ProjectRelativePath)))
            self.need_sync_source_files.extend(self.get_sync_file(
                "{0}/{1}.uproject".format(self.build_data.ProjectRelativePath, self.build_data.ProjectName)))
            self.sync_source()
            need_sync_content = [
                "{0}/Content/".format(self.build_data.ProjectRelativePath),
                "{0}/Config/".format(self.build_data.ProjectRelativePath),
                "{0}/Scripts/".format(self.build_data.ProjectRelativePath),
                "{0}/Build/".format(self.build_data.ProjectRelativePath),
                "S1GameServer/"
            ]
            sync_content_process = self.sync_content(*need_sync_content)

        if self.build_data.build_editor:
            self.build_editor()
        if self.build_data.build_game:
            self.build_game()
        if self.build_data.replace_target is not False:
            self.replace_target()
        if self.build_data.start_game:
            self.start_game()

        if self.build_data.sync and sync_content_process is not None:
            while sync_content_process.poll() is None:
                output = sync_content_process.stdout.readline().rstrip().decode('utf-8')
                if output == '' and sync_content_process.poll() is not None:
                    break
                if len(output) > 0:
                    print(output)
        print("finished")

        self.build_data.step = -1

    def sync_content(self, *relation_path):
        cmd = 'p4 -I -C utf8 sync '
        for x in relation_path:
            cmd += self.get_client_stream_param(x)
            cmd += " "
        print(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        return process

    def sync_source(self):
        self.build_data.step = 1
        self.build_data.progress_value = 0

        if len(self.need_sync_source_files) == 0:
            return
        step_value = 99.0 / len(self.need_sync_source_files)

        for file in self.need_sync_source_files:
            cmd = 'p4 -I -C utf8 sync {0} '.format(file)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
            print("exec:" + cmd)
            while process.poll() is None:
                output = process.stdout.readline().rstrip().decode('utf-8')
                if output == '' and process.poll() is not None:
                    break

            self.build_data.progress_value += step_value

    def build_game(self):
        self.build_data.step = 3
        self.build_data.progress_value = 0

        UAT_Path = os.path.join(self.build_data.ClientRoot, "UE5EA", "Engine", "Build", "BatchFiles", "RunUAT.bat")
        CMD_Params = "BuildCookRun -project={0}/{1}/{1}.uproject -platform=Win64 -target={1} -clientconfig={2}".format(
            self.build_data.ClientRoot, "S1Game", "Test")

        CMD_Params += " -noP4 -stdout -UTF8Output -Build -SkipCook -SkipStage -SkipPackage"
        CMD_Params += " -skipbuildeditor -nobootstrapexe"

        print(UAT_Path)
        print(CMD_Params)
        process = subprocess.Popen("{0} {1}".format(UAT_Path, CMD_Params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        while process.poll() is None:
            try:
                output = process.stdout.readline().rstrip().decode('UTF8')
                if output == '' and process.poll() is not None:
                    break
                if len(output) > 0:
                    print(output)
            except:
                print('e')

    def build_editor(self):
        self.build_data.step = 2
        self.build_data.progress_value = 0

        root_path = self.build_data.ClientRoot
        process = subprocess.Popen("{0}\S1Game\GenerateProjectFiles.bat".format(root_path), shell=True, stdout=None,
                                   encoding="UTF8")
        process.communicate()

        bat = "{0}/UE5EA/Engine/Build/BatchFiles/Build.bat".format(root_path)
        params = " -Target=S1GameEditor Win64 Development"
        params += " -Project={0}/S1Game/S1Game.uproject".format(root_path)
        params += ' -Target="ShaderCompileWorker Win64 Development -Quiet"'
        params += " -WaitMutex -FromMsBuild"

        process = subprocess.Popen("{0} {1}".format(bat, params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        while process.poll() is None:
            try:
                output: str = process.stdout.readline().rstrip().decode('UTF8')
                if output == '' and process.poll() is not None:
                    break
                # ------ Building 3 action(s) started ------
                #
                if len(output) > 0:
                    if output.startswith('['):
                        word = output[1:output.index("]", 1)]
                        word = word.split("/")
                        a = int(word[0])
                        b = int(word[1])
                        if b > 0:
                            self.build_data.progress_value = a / b
            except:
                pass

            sleep(0.01)

    def replace_target(self):
        self.build_data.step = 4
        self.build_data.progress_value = 0

        game_path = os.path.join(self.build_data.ClientRoot, "S1Game", "Binaries", "Win64",
                                 "S1Game-Win64-Test.exe")
        target_path = os.path.join(self.build_data.replace_target, "S1Game", "Binaries", "Win64",
                                   "S1Game-Win64-Test.exe")

        if os.path.exists(target_path):
            os.remove(target_path)
        shutil.copyfile(game_path, target_path)

        self.build_data.progress_value = 1

    def start_game(self):
        cmd = "S1Game"
        subprocess.Popen(cmd, shell=True)

    def get_client_stream_param(self, relation_path):
        client_stream = self.build_data.ClientStream
        if not client_stream.endswith("/"):
            client_stream += "/"
        if len(relation_path) > 0:
            client_stream += relation_path
        if relation_path[-1] == "/":
            client_stream += "..."

        changelist = "@" + self.build_data.ChangeList
        if self.build_data.ChangeList == "":
            changelist = "#head"
        client_stream += changelist

        return client_stream

    def get_sync_file(self, relation_path: str):
        result: [str] = []
        client_stream = self.get_client_stream_param(relation_path)
        p = subprocess.run(['p4', 'sync', '-n', client_stream], capture_output=True, text=True)
        files = p.stdout.splitlines()
        for f in files:
            if " - " in f:
                a = f.split(" - ")
                result.append(a[0])
        return result


def main():
    view = MainView()


main()

"""
build_system = BuildSystem(build_setting)
    build_system.init_p4()

    if build_context.sync:
        build_system.sync('UE5EA', build_context.changelist)
        if build_context.build_editor or build_context.build_game:
            build_system.sync("S1Game/Source", build_context.changelist)
            build_system.sync("S1Game/Plugins", build_context.changelist)
            build_system.sync("S1Game/Config", build_context.changelist)
        else:
            build_system.sync("S1Game", build_context.changelist)

    if build_context.build_editor:
        build_system.build_editor()
    if build_context.build_game:
        build_system.build_game()

    if build_context.sync:
        if build_context.build_editor or build_context.build_exe:
            build_system.sync("S1Game/Content", build_context.changelist)
            build_system.sync("S1Game/Scripts", build_context.changelist)
"""

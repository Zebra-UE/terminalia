import datetime
import shutil
import threading
import tkinter as tk
import subprocess
import os
import tkinter.filedialog
from datetime import time, datetime
from threading import Thread
import time
from tkinter import ttk
from enum import Enum
from multiprocessing import Queue, Process

BuildStep = Enum("BuildStep",
                 ['Undefined',
                  "Ready",
                  "Get_Changelist",
                  "Sync_Source_Size",
                  "Sync_Source",
                  "Build_Editor",
                  "Build_Game",
                  "BuildFinished",
                  "Replace_Target",
                  "Start_Game",
                  "Sync_Content",
                  "Finished"])


class ProgressValue:

    def __init__(self, current=0, total=0):
        self.current = 0
        self.total = 0
        self.set(current, total)

    def step(self, num):
        self.current += num

    def set(self, current, total):
        self.current = current
        self.total = total

    def get(self):
        if self.total == 0:
            return 0

        return (self.current / self.total) * 100


class EventData:
    def __init__(self):
        self.event_data = []
        self.event_index = 0

    def info(self, s):
        self.event_data.append("info: " + s)

    def error(self, e):
        self.event_data.append("error: " + e)

    def clean(self):
        self.event_data = []
        self.event_index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.event_index < len(self.event_data):
            x = self.event_data[self.event_index]
            self.event_index += 1
            return x
        else:
            raise StopIteration


class BuildData:
    def __init__(self):
        self.P4PORT = ""
        self.P4USER = ""
        self.P4CLIENT = ""

        self.ClientRoot = ""
        self.EngineRelativePath = "UE5EA"

        self.ProjectName = ""

        self.ClientStream = ""
        self.ChangeList = ""
        self.GameConfig = ""
        self.TargetPath = "D:/Game/"

        self.sync = False
        self.build_editor = False
        self.build_game = False
        self.replace_target: bool = False
        self.start_game: bool = False
        self.enable_trace: bool = False
        self.additive_game_param: str = ""

        self.start_server: bool = False

        self.target_path: str = ""




def save_build_data(build_data: BuildData):
    value = "{0}\n{1}\n{2}\n".format(build_data.P4PORT, build_data.P4USER, build_data.P4CLIENT)
    with open('settings.ini', 'w', encoding='UTF8') as f:
        f.write(value)


class ViewData:
    def __init__(self):
        self.step: BuildStep = BuildStep.Undefined
        self.progress_value = ProgressValue()

        self.event_data: EventData = EventData()


class SyncRequest:
    def __init__(self):
        self.path: [str] = []

    def add_path(self, path):
        self.path.append(path)

    def clean(self):
        self.path.clear()


class BuildEditorRequest:
    def __init__(self):
        self.EnginePathName = ""
        self.ProjectName = ""
        self.BuildConfig = ""


class BuildGameRequest:
    def __init__(self):
        self.ClientPath = ""
        self.EnginePath = ""
        self.ProjectName = ""
        self.BuildConfig = ""


class ReplaceTargetRequest:
    def __init__(self):
        self.name = ""
        self.ext_list = ""
        self.game_path = ""
        self.target_path = ""


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


class BuildProcess(Process):
    def __init__(self, build_data: BuildData, message_queue: Queue):
        super().__init__()
        self.build_data = build_data
        self.message_queue = message_queue

        self.sync_content_process: SyncContentProcess = None

    def get_latest_changelist(self):
        output = subprocess.check_output("p4 changes -m 1 -s submitted", encoding='utf-8', errors='ignore')
        output = output.strip()
        output = output.split()
        if output[0] == 'Change':
            return output[1]

        raise Exception("change fail")

    def init(self):

        subprocess.check_output('p4 set P4PORT={0}'.format(self.build_data.P4PORT))
        subprocess.check_output('p4 set P4USER={0}'.format(self.build_data.P4USER))
        subprocess.check_output('p4 set P4CLIENT={0}'.format(self.build_data.P4CLIENT))

        output = subprocess.check_output('p4 info', encoding='utf-8')
        output = output.strip()
        output = output.split("\n")
        for line in output:
            line = line.strip()
            if line.startswith("Client root:"):
                self.build_data.ClientRoot = line[len("Client root:") + 1:].strip()
            elif line.startswith("Client stream:"):
                self.build_data.ClientStream = line[len("Client stream:") + 1:].strip()

        if self.build_data.sync:
            changelist = self.build_data.ChangeList
            if len(changelist) == 0:
                self.message_queue.put(UIMessage("get latest changelist"))
                changelist = self.get_latest_changelist()
                self.message_queue.put(UIMessage("get latest changelist:{0}".format(changelist)))
                self.message_queue.put(UIProgress(BuildStep.Get_Changelist,  int(changelist),0))
            self.build_data.ChangeList = changelist
        else:
            f = os.path.join(self.build_data.ClientRoot, "changelist.txt")
            with open(f, "r", encoding="utf8") as f:
                changelist = f.readline()
                changelist = changelist.strip()
                self.build_data.ChangeList = changelist

        project_path = os.path.join(self.build_data.ClientRoot, "S1Game")
        for f in os.listdir(project_path):
            if f.endswith(".uproject"):
                self.build_data.ProjectName = f[:-9]

    def run(self):
        self.init()
        self.message_queue.put(UIMessage("start"))
        if self.build_data.sync:
            request = SyncRequest()
            request.add_path("UE5EA/")
            request.add_path("{0}/Source/".format("S1Game"))
            request.add_path("{0}/Plugins/".format("S1Game"))
            request.add_path(
                "{0}/{1}.uproject".format("S1Game", self.build_data.ProjectName))

            self.sync_source(request)
            self.sync_save()

            request = SyncRequest()
            request.add_path("{0}/Content/".format("S1Game"))
            request.add_path("{0}/Config/".format("S1Game"))
            request.add_path("{0}/Scripts/".format("S1Game"))
            request.add_path("{0}/Build/".format("S1Game"))
            request.add_path("S1GameServer")
            self.sync_content(request)

        if self.build_data.build_editor:
            request = BuildEditorRequest()
            request.EnginePathName = "UE5EA"
            request.ProjectName = self.build_data.ProjectName
            request.BuildConfig = "Development"
            self.build_editor(request)

        if self.build_data.build_game:
            request = BuildGameRequest()
            request.ClientPath = os.path.join(self.build_data.ClientRoot,"S1Game")
            request.ProjectName = self.build_data.ProjectName
            request.BuildConfig = "Development"
            request.EnginePathName = os.path.join(self.build_data.ClientRoot,"UE5EA")
            self.build_game(request)

        self.message_queue.put(UIProgress(BuildStep.BuildFinished, 0, 0))

        if self.build_data.replace_target:
            q = ReplaceTargetRequest()
            self.replace_target(q)

        if self.build_data.start_game:
            self.start_game()
        if self.build_data.start_server:
            self.start_server()

        if self.build_data.sync and self.sync_content_process is not None:
            while self.sync_content_process.is_alive():
                pass

        self.message_queue.put(UIProgress(BuildStep.Finished, 0, 0))

    def sync_source(self, request: SyncRequest):

        self.message_queue.put(UIMessage("sync source"))

        self.message_queue.put(UIProgress(BuildStep.Sync_Source, 0, 0))

        cmd = 'p4 sync -N'
        depot_path = ""
        for x in request.path:
            depot_path += self.get_client_stream_param(x)
            depot_path += " "

        output: str = subprocess.check_output(cmd + " " + depot_path, encoding='utf-8')

        change_file_num = [0, 0, 0]
        if output.startswith("Server network estimates:"):
            output = output[len("Server network estimates: "):]
            l = output.split(",")
            x = l[0][len("files added/updated/deleted="):]
            x = x.split("/")

            for i in range(3):
                change_file_num[i] = int(x[i])
        else:
            raise Exception("Server network estimates not yet implemented")

        self.message_queue.put(UIMessage(
            "add:{0},updated:{1},deleted:{2}".format(change_file_num[0], change_file_num[1], change_file_num[2])))

        total = change_file_num[0] + change_file_num[1] + change_file_num[2]
        self.message_queue.put(
            UIProgress(BuildStep.Sync_Source, 0, total))

        if total > 0:
            current = 0
            cmd = 'p4 -I -C utf8 sync {0}'.format(depot_path)

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
            process.daemon = True

            for line in self.read_process_output(process):
                if self.update_sync_progress(line):
                    current += 1
                    self.message_queue.put(UIProgress(BuildStep.Sync_Source, current, total))

    def sync_save(self):
        changelist_txt = os.path.join(self.build_data.ClientRoot, "changelist.txt")
        if os.path.exists(changelist_txt):
            os.remove(changelist_txt)
        with open(changelist_txt, mode="w", encoding='utf8') as f:
            f.write(self.build_data.ChangeList)

    def sync_content(self, request: SyncRequest):
        paths = []
        for x in request.path:
            paths.append(self.get_client_stream_param(x))
        self.sync_content_process = SyncContentProcess(self.message_queue,*paths)
        self.sync_content_process.start()

    def build_editor(self, request: BuildEditorRequest):
        self.message_queue.put(UIProgress(BuildStep.Build_Editor, 0, 0))

        root_path = self.build_data.ClientRoot
        project_file = os.path.join(root_path, request.ProjectName, "{0}.uproject".format(request.ProjectName))

        def generate_project_files():

            engine_batch = os.path.join(root_path, request.EnginePathName, "Engine", "Build", "BatchFiles",
                                        "GenerateProjectFiles.bat")

            if os.path.exists(engine_batch):
                cmd = [engine_batch, project_file, "-VisualStudio2022", "-Game", "-Engine", "-Programs"]
                p = subprocess.Popen(cmd, shell=True, stdout=None, encoding="UTF8")
                p.communicate()

        generate_project_files()

        bat = "{0}/{1}/Engine/Build/BatchFiles/Build.bat".format(root_path, request.EnginePathName)
        params = " -Target={0}Editor Win64 {1}".format(request.ProjectName, request.BuildConfig)
        params += " -Project={0}".format(project_file)
        params += ' -Target="ShaderCompileWorker Win64 Development -Quiet"'
        params += " -WaitMutex -FromMsBuild"

        process = subprocess.Popen("{0} {1}".format(bat, params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        process.daemon = True
        find_total = -1
        base_total = -1
        while process.poll() is None:
            try:
                output: str = process.stdout.readline().rstrip().decode('UTF8')
                if output == '' and process.poll() is not None:
                    break

                if len(output) > 0:
                    self.update_build_progress(output)

            except:
                pass

    def build_game(self, request: BuildGameRequest):

        self.message_queue.put(UIProgress(BuildStep.Build_Game, 0, 0))
        self.build_data.progress_value = ProgressValue(0, 0)

        UAT_Path = os.path.join(request.EnginePath, "Engine", "Build", "BatchFiles",
                                "RunUAT.bat")

        CMD_Params = "BuildCookRun -project={0}/{1}.uproject -platform=Win64 -target={1} -clientconfig={2}".format(
            request.ClientPath, request.ProjectName, request.BuildConfig)

        CMD_Params += " -noP4 -stdout -UTF8Output -Build -SkipCook -SkipStage -SkipPackage"
        CMD_Params += " -skipbuildeditor -nobootstrapexe"

        game_path = os.path.join(request.ClientPath, "Binaries", "Win64", self.get_build_output_name())
        if os.path.exists(game_path):
            self.message_queue.put(UIMessage("remove {0}".format(game_path)))
            os.remove(game_path)

        self.message_queue.put(UIMessage("build game Win64 {0}".format(self.build_data.GameConfig)))

        process = subprocess.Popen("{0} {1}".format(UAT_Path, CMD_Params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        error_text = []
        while process.poll() is None:
            output = process.stdout.readline().rstrip().decode('UTF8', errors='ignore')
            if output == '' and process.poll() is not None:
                break
            if len(output) > 0:
                self.update_build_progress(output)
                if "error" in output:
                    print(output)

                    error_text.append(output)
            time.sleep(0.01)

        time.sleep(2.0)
        if not os.path.exists(game_path):
            for x in error_text:
                print(x)


    def update_build_progress(self, output):
        if output.startswith('['):
            word = output[1:output.index("]", 1)]
            word = word.split("/")
            if len(word) == 2:
                a = int(word[0])
                b = int(word[1])
                if b > 0:
                    self.message_queue.put(UIProgress(BuildStep.Build_Game, a, b))

    def update_sync_progress(self, output):
        return "- updating" in output or "- added as" in output or "- deleted as" in output

    def read_process_output(self, process):
        while process.poll() is None:
            output: str = process.stdout.readline().rstrip().decode('UTF8')
            if output == '' and process.poll() is not None:
                break
            if len(output) > 0:
                yield output
            time.sleep(0.1)

    def get_build_output_name(self, ext="exe"):
        if self.build_data.GameConfig == "Development":
            return "{0}.{1}".format(self.build_data.ProjectName, ext)
        else:
            return "{0}-Win64-{1}.{2}".format(self.build_data.ProjectName, self.build_data.GameConfig, ext)

    def replace_target(self, request: ReplaceTargetRequest):
        self.view_data.step = BuildStep.Replace_Target
        self.view_data.progress_value = ProgressValue(0, 2)

        game_path = os.path.join(self.build_data.ClientRoot, "S1Game", "Binaries", "Win64",
                                 self.get_build_output_name())
        pdb_path = os.path.join(self.build_data.ClientRoot, "S1Game", "Binaries", "Win64",
                                self.get_build_output_name("pdb"))
        target_game_path = self.build_data.target_path
        target_pdb_path = os.path.join(os.path.dirname(target_game_path), os.path.basename(pdb_path))

        if target_game_path is not None:
            if os.path.exists(target_game_path):
                os.remove(target_game_path)
            if os.path.exists(target_pdb_path):
                os.remove(target_pdb_path)
            print("copy {0}".format(game_path))
            print("target:{0}".format(target_game_path))
            shutil.copyfile(game_path, target_game_path)
            shutil.copyfile(pdb_path, target_pdb_path)

        self.view_data.progress_value.step(1)

    def start_game(self):
        exe_path = self.build_data.target_path
        params = self.build_data.additive_game_param.split()

        if self.build_data.enable_trace:
            params.append("-trace=gpu,cpu,frame,log,bookmark,task,ContextSwitch")

        argument = ""
        if len(params) > 0:
            if self.build_data.enable_trace:
                argument = "-ArgumentList '"
                argument += " ".join(['"{0}"'.format(x) for x in params])
                argument += "'"
            else:
                argument = " ".join(["{0}".format(x) for x in params])

        if exe_path is not None:

            if self.build_data.enable_trace:
                cmd = ["powershell", "Start-Process", exe_path, argument, "-Verb", "RunAs"]
            else:
                cmd = ["start", exe_path, argument]

            self.view_data.event_data.info("start game {0}".format(exe_path))
            try:
                subprocess.Popen(cmd, shell=True)
            except:
                pass

    def start_server(self):
        server_script_path = os.path.join(self.build_data.ClientRoot, "S1GameServer", "bin")
        server_script_path = server_script_path.replace("\\", "/")
        if server_script_path[1] == ":":
            server_script_path = "/mnt/" + server_script_path[0].lower() + server_script_path[2:]
        cmd = ["start", "wsl", "bash", "-c", "'cd {0} && {1}'".format(server_script_path, "./start.py")]
        # "wsl bash -c 'cd /path/to/directory && ./your_program'"

        print(" ".join(cmd))
        self.view_data.event_data.info("start server @ {0}".format(server_script_path))
        try:
            subprocess.Popen(cmd, shell=True)
        except:
            pass

    def stop_server(self):
        pass

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

        client_stream = self.get_client_stream_param(relation_path)

        p = subprocess.run(['p4', 'sync', '-n', client_stream], capture_output=True, text=True)

        files = p.stdout.splitlines()
        result = []
        for f in files:

            if " - " in f:
                a = f.split(" - ")
                if len(a) == 2:
                    if a[1].startswith("added as") or a[1].startswith("updating"):
                        result.append(a[0])
                    elif a[1].startswith("deleted as"):
                        b = a[0]
                        b = b[0:b.rfind('#')]
                        b += "@{0}".format(self.build_data.ChangeList)
                        result.append(b)
                    else:
                        print(f)
            else:
                print(f)

        return result


class BuildSystem:
    def __init__(self):
        self.message_queue = Queue()
        self.build_data = BuildData()
        self.build_process: Process = None
        self.ui_tread: Thread = None

        self.load_build_data()

    def load_build_data(self):
        if os.path.exists('settings.ini'):
            with open('settings.ini', 'r', encoding='UTF8') as f:
                lines = f.readlines()
                self.build_data.P4PORT = lines[0].strip(" \n")
                self.build_data.P4USER = lines[1].strip(" \n")
                self.build_data.P4CLIENT = lines[2].strip(" \n")

    def Start(self):
        if self.build_process is None:
            self.build_process = BuildProcess(self.build_data, self.message_queue)

            self.build_process.start()

    def Stop(self):
        if self.ui_tread is not None:
            self.message_queue.put(UIProgress(BuildStep.Finished, 0, 0))




    def MainLoop(self, view: tk.Tk):
        if self.ui_tread is None:
            self.ui_tread = UIThread(view, self.message_queue)
            self.ui_tread.start()
        view.mainloop()


class MainView(tk.Tk):
    def __init__(self, system: BuildSystem):
        tk.Tk.__init__(self)
        self.system: BuildSystem = system

        self.view_data = ViewData()
        self.tk_P4PORT = tk.StringVar()
        self.tk_P4USER = tk.StringVar()
        self.tk_P4CLIENT = tk.StringVar()
        self.tk_sync = tk.IntVar()
        self.tk_build_editor = tk.IntVar()
        self.tk_build_exe = tk.IntVar()
        self.tk_replace = tk.IntVar()
        self.tk_start_game = tk.IntVar()
        self.tk_change_list = tk.StringVar()
        self.tk_start_server = tk.IntVar()
        self.progress_bar = None
        self.tk_step_text = tk.StringVar()
        self.tk_progress_text = tk.StringVar()

        self.cached_progress_text = ""
        self.dot_text = ""
        self.dot_time = 0
        self.tk_game_config_combobox = None
        self.tk_start_game_trace = tk.IntVar()
        self.tk_start_game_command = tk.StringVar()

        self.tk_event_index = -1
        self.tk_event_listview: tk.Listbox = None

        self.left_tree = None

        self.geometry("700x500")
        self.read_default()
        self.create_view()

    def destroy(self):
        super().destroy()
        self.system.Stop()

    def read_default(self):
        self.tk_P4PORT.set(self.system.build_data.P4PORT)
        self.tk_P4USER.set(self.system.build_data.P4USER)
        self.tk_P4CLIENT.set(self.system.build_data.P4CLIENT)

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

        i = self.left_tree.add_child(
            tk.Checkbutton(left_frame, text="5. start game,with cmd:", variable=self.tk_start_game, bg=row_bg,
                           command=lambda: self.switch_start_game_checkbox()))
        self.left_tree.add_child(tk.Checkbutton(left_frame, text="trace", bg=row_bg, variable=self.tk_start_game_trace),
                                 parent=i)
        self.left_tree.add_child(tk.Entry(left_frame, textvariable=self.tk_start_game_command), parent=i)

        self.left_tree.add_child(
            tk.Checkbutton(left_frame, text="6. start server", bg=row_bg, variable=self.tk_start_server))

        self.left_tree.update()

        b = tk.Button(left_frame, text='Build', font=('Arial', 10), width=10, height=1,
                      command=lambda: self.run())
        b.place(x=10, y=400)

        right_frame = tk.Frame(self, bg="beige")
        right_frame.place(x=220, y=60, width=480, height=440)
        self.tk_event_listview = tk.Listbox(right_frame, bg="beige")
        self.tk_event_listview.place(x=0, y=0, height=380, width=480)

        self.tk_step_text.set("waiting...")
        c = tk.Label(right_frame, textvariable=self.tk_step_text, font=('Arial', 8), bg="beige")
        c.place(x=20, y=380)

        self.tk_progress_text.set("/")
        d = tk.Label(right_frame, textvariable=self.tk_progress_text, font=('Arial', 8), bg="beige")
        d.place(x=220, y=400)
        self.progress_bar = ttk.Progressbar(right_frame)
        self.progress_bar.place(x=10, y=420, width=460, height=12)

    def switch_sync_checkbox(self):
        if self.tk_sync.get():
            self.left_tree.expand(0)
            self.update()
        else:
            self.left_tree.collect(0)

    def switch_build_game_checkbox(self):
        if self.tk_build_exe.get():
            self.left_tree.expand(3)
        else:
            self.left_tree.collect(3)

    def switch_start_game_checkbox(self):
        if self.tk_start_game.get():
            self.left_tree.expand(6)
        else:
            self.left_tree.collect(6)

    def step(self):
        self.system.build_data.P4USER = self.tk_P4USER.get()
        self.system.build_data.P4PORT = self.tk_P4PORT.get()
        self.system.build_data.P4CLIENT = self.tk_P4CLIENT.get()
        self.system.build_data.sync = self.tk_sync.get()
        self.system.build_data.ChangeList = self.tk_change_list.get()
        self.system.build_data.build_editor = self.tk_build_editor.get()
        self.system.build_data.build_game = self.tk_build_exe.get()
        self.system.build_data.GameConfig = self.tk_game_config_combobox.get()
        self.system.build_data.replace_target = self.tk_replace.get()
        self.system.build_data.start_game = self.tk_start_game.get()
        self.system.build_data.enable_trace = self.tk_start_game_trace.get()
        self.system.build_data.additive_game_param = self.tk_start_game_command.get()
        self.system.build_data.start_server = self.tk_start_server.get()

    def run(self):
        self.step()
        self.system.Start()

    def finished(self):
        pass


class UIProgress:
    def __init__(self, step, current, total):
        self.step = step
        self.current = current
        self.total = total


class UIMessage:
    def __init__(self, message):
        self.message = message


class UIThread(threading.Thread):
    def __init__(self, view: MainView, message_queue):
        threading.Thread.__init__(self)
        self.view: MainView = view
        self.message_queue: Queue = message_queue

        self.progress_value = 0
        self.bNeedExit = False
        self.current_step = BuildStep.Undefined
        self.bNeedShowSyncContentProgress = False
        self.sync_content_progress = UIProgress(BuildStep.Sync_Content, 0, 0)

    def run(self):
        while not self.bNeedExit:
            if self.message_queue.qsize() > 0:
                item = self.message_queue.get(block=True, timeout=1)
                if isinstance(item, UIProgress):
                    self.refresh_progress(item)
                elif isinstance(item, UIMessage):
                    self.refresh_message(item)
                self.view.update()

        self.view.finished()

    def refresh_message(self, item: UIMessage):
        self.view.tk_event_listview.insert(tk.END, item.message)

    def refresh_progress(self, item: UIProgress):

        if item.total > 0:
            if item.step != BuildStep.Sync_Content or self.bNeedShowSyncContentProgress:
                current_progress_value = item.current / item.total
                delta = current_progress_value - self.progress_value
                self.view.progress_bar.step(delta)
                self.progress_value = current_progress_value
            elif item.step == BuildStep.Sync_Content:
                self.sync_content_progress = item

        elif item.step != BuildStep.Undefined:
            if item.step != self.current_step:
                self.current_step = item.step
                if self.current_step == BuildStep.Sync_Source:
                    self.view.tk_step_text.set("sync source")
                elif self.current_step == BuildStep.Build_Editor:
                    self.view.tk_step_text.set("build editor")
                elif self.current_step == BuildStep.Finished:
                    self.view.tk_step_text.set("Finished")

            if item.step == BuildStep.BuildFinished:
                self.bNeedShowSyncContentProgress = True
            if item.step == BuildStep.Finished:
                self.bNeedExit = True
            if item.step == BuildStep.Get_Changelist:
                self.view.tk_change_list.set(str(item.current))


class SyncContentProcess(Process):
    def __init__(self,message_queue, *request_paths):
        super().__init__()
        self.message_queue = message_queue
        self.request_paths = request_paths

    def run(self):
        self.message_queue.put(UIMessage("sync context"))
        cmd = 'p4 -I -C utf8 sync '
        for x in self.request_paths:
            cmd += x
            cmd += " "

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        process.daemon = True


def main():
    system = BuildSystem()
    view = MainView(system)
    system.MainLoop(view)


if __name__ == "__main__":
    main()

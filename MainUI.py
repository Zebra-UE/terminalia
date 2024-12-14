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

from typing import Dict


class EStageName(Enum):
    Begin = 0,
    SyncSource = 1,
    SyncContext = 2,
    BuildEditor = 3,
    BuildGame = 4,
    Exit = 100


class UIMessageData:
    def __init__(self, message):
        self.message = message


class UIStageData:
    def __init__(self, stage, current, total):
        self.stage = stage
        self.current = current
        self.total = total





class ViewData:
    def __init__(self):
        self.P4PORT = ""
        self.P4USER = ""
        self.P4CLIENT = ""
        self.ChangeList = ""
        self.GameConfig = ""

        self.sync = False
        self.build_editor = False
        self.build_game = False
        self.replace_target: bool = False
        self.start_game: bool = False
        self.enable_trace: bool = False
        self.additive_game_param: str = ""

        self.start_server: bool = False


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


class BuildContext:
    def __init__(self):
        self.event_queue = Queue()
        self.message_queue = Queue()
        self.view_data = ViewData()
        self.load_view_data()

    def load_view_data(self):
        if os.path.exists('settings.ini'):
            with open('settings.ini', 'r', encoding='UTF8') as f:
                lines = f.readlines()
                self.view_data.P4PORT = lines[0].strip(" \n")
                self.view_data.P4USER = lines[1].strip(" \n")
                self.view_data.P4CLIENT = lines[2].strip(" \n")

    def save_view_data(self):
        with open('settings.ini', 'w', encoding='UTF8') as f:
            f.writelines([self.view_data.P4PORT + "\n", self.view_data.P4USER + "\n", self.view_data.P4CLIENT + "\n"])


class MainView(tk.Tk):
    def __init__(self, context: BuildContext):
        tk.Tk.__init__(self)
        self.context: BuildContext = context
        self.ui_tread = None
        self.launch_thread = None
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

    def read_default(self):
        self.tk_P4PORT.set(self.context.view_data.P4PORT)
        self.tk_P4USER.set(self.context.view_data.P4USER)
        self.tk_P4CLIENT.set(self.context.view_data.P4CLIENT)

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
        self.context.view_data.P4USER = self.tk_P4USER.get()
        self.context.view_data.P4PORT = self.tk_P4PORT.get()
        self.context.view_data.P4CLIENT = self.tk_P4CLIENT.get()
        self.context.view_data.sync = self.tk_sync.get()
        self.context.view_data.ChangeList = self.tk_change_list.get()
        self.context.view_data.build_editor = self.tk_build_editor.get()
        self.context.view_data.build_game = self.tk_build_exe.get()
        self.context.view_data.GameConfig = self.tk_game_config_combobox.get()
        self.context.view_data.replace_target = self.tk_replace.get()
        self.context.view_data.start_game = self.tk_start_game.get()
        self.context.view_data.enable_trace = self.tk_start_game_trace.get()
        self.context.view_data.additive_game_param = self.tk_start_game_command.get()
        self.context.view_data.start_server = self.tk_start_server.get()

    def run(self):
        if self.launch_thread is not None and self.launch_thread.is_alive():
            return

        self.step()
        self.context.save_view_data()

        if self.ui_tread is None:
            self.ui_tread = UIThread(self, self.context.message_queue)
            self.ui_tread.start()

        if self.launch_thread is None:
            self.launch_thread = LaunchThread(self.context)
            self.launch_thread.start()

class UIStageStatistics:
    def __init__(self):
        self.progress = 0
        self.current = 0
        self.total = 0
        self.start_time = time.time()
        self.end_time = 0
        self.print_time = self.start_time

class UIThread(threading.Thread):
    def __init__(self, view: MainView, message_queue):
        threading.Thread.__init__(self)
        self.view: MainView = view
        self.message_queue: Queue = message_queue

    def on_stage_begin(self,stage):
        return "begin " + self.get_stage_text(stage)
    def on_stage_end(self,stage):
        return "end " + self.get_stage_text(stage)
    def get_stage_text(self,stage):
        if stage == EStageName.SyncContext:
            return "sync content"
        elif stage == EStageName.SyncSource:
            return "sync source"
        elif stage == EStageName.BuildGame:
            return "build game"
        elif stage == EStageName.BuildEditor:
            return "build editor"
        return "unkown"
    def run(self):

        stage_statistics:Dict[EStageName, UIStageStatistics] = dict()
        do_something = False
        current_progress_value = 0
        need_exit = False
        while True:
            if not self.message_queue.empty():
                do_something = True
                item = self.message_queue.get(block=False)
                if isinstance(item, UIStageData):
                    if item.stage not in stage_statistics:
                        stage_statistics[item.stage] = UIStageStatistics()
                        self.view.tk_event_listview.insert(tk.END,self.on_stage_begin(stage))
                    stage_statistics[item.stage].progress = item.current / item.total
                    stage_statistics[item.stage].current = item.current
                    stage_statistics[item.stage].total = item.total

                    if item.current == item.total:
                        stage_statistics[item.stage].end_time = time.time()
                        self.view.tk_event_listview.insert(tk.END, self.on_stage_end(stage))
                    if item.stage == EStageName.Exit:
                        need_exit = True

            if self.message_queue.empty() and do_something:
                do_something = False
                progress = 0
                current_stage = EStageName.Begin
                for stage, statistics in stage_statistics.items():
                    if statistics.end_time == 0:
                        if current_stage == EStageName.Begin:
                            current_stage = stage
                            progress = statistics.progress
                        elif current_stage == EStageName.SyncContext:
                            current_stage = stage
                            progress = statistics.progress

                        current_time = time.time()
                        if current_time - statistics.print_time > 10.0:
                            statistics.print_time = current_time
                            self.view.tk_event_listview.insert(tk.END,
                                                               "{2}:{0}/{1}".format(statistics.current, statistics.total,self.get_stage_text(stage)))
                delta = progress - current_progress_value
                self.view.progress_bar.step(delta)
                self.view.update()

            if need_exit and not do_something:
                break

class SyncData:
    def __init__(self):
        self.ClientStream = ""
        self.ChangeList = ""
        self.source_path = []
        self.content_path = []


class BuildData:
    def __init__(self):
        self.build_editor = False
        self.build_game = False

        self.ProjectPath = ""
        self.ProjectName = ""
        self.EnginePath = ""
        self.GameBuildConfig = ""


class P4:
    def __init__(self):
        self.ClientRoot = ""
        self.ClientStream = ""
        self.Head = ""


class LaunchThread(threading.Thread):
    def __init__(self, context):
        super().__init__()
        self.context: BuildContext = context
        self.p4 = P4()

    def init_p4(self):
        subprocess.check_output('p4 set P4PORT={0}'.format(self.context.view_data.P4PORT))
        subprocess.check_output('p4 set P4USER={0}'.format(self.context.view_data.P4USER))
        subprocess.check_output('p4 set P4CLIENT={0}'.format(self.context.view_data.P4CLIENT))
        output = subprocess.check_output('p4 info', encoding='utf-8')
        output = output.strip()
        output = output.split("\n")
        for line in output:
            line = line.strip()
            if line.startswith("Client root:"):
                self.p4.ClientRoot = line[len("Client root:") + 1:].strip()
            elif line.startswith("Client stream:"):
                self.p4.ClientStream = line[len("Client stream:") + 1:].strip()

        output = subprocess.check_output("p4 changes -m 1 -s submitted", encoding='utf-8', errors='ignore')
        output = output.strip()
        output = output.split()
        if output[0] == 'Change':
            self.p4.Head = output[1]

    def run(self):
        self.init_p4()

        project_name = ""
        project_path = os.path.join(self.p4.ClientRoot, "S1Game")
        for f in os.listdir(project_path):
            if f.endswith(".uproject"):
                project_name = f[:-9]

        if self.context.view_data.sync:
            sync_data: SyncData = SyncData()
            sync_data.ClientStream = self.p4.ClientStream
            sync_data.ChangeList = self.context.view_data.ChangeList if len(
                self.context.view_data.ChangeList) > 0 else self.p4.Head
            sync_data.source_path.append("UE5EA/")
            sync_data.source_path.append("{0}/Source/".format(project_name))
            sync_data.source_path.append("{0}/Plugins/".format(project_name))
            sync_data.source_path.append(
                "{0}/{1}.uproject".format(project_name, project_name))
            sync_data.content_path.append("{0}/Content/".format("S1Game"))
            sync_data.content_path.append("{0}/Config/".format("S1Game"))
            sync_data.content_path.append("{0}/Scripts/".format("S1Game"))
            sync_data.content_path.append("{0}/Build/".format("S1Game"))
            sync_data.content_path.append("S1GameServer")
            sync_process = SyncProcess(sync_data, self.context.event_queue)
            sync_process.start()

        sync_finished = False
        build_finished = False
        need_build = self.context.view_data.build_game or self.context.view_data.build_editor
        if not self.context.view_data.sync:
            sync_finished = True
            if need_build:
                self.start_build(project_name)

        while True:
            if not self.context.event_queue.empty():
                item = self.context.event_queue.get(block=True, timeout=1)
                self.context.message_queue.put(item)

                if isinstance(item, EventData):
                    if item.event == EventEnum.SyncSourceFinished:
                        if need_build:
                            self.start_build(project_name)
                        else:
                            build_finished = True
                    elif item.event == EventEnum.SyncFinished:
                        sync_finished = True
                    elif item.event == EventEnum.BuildFinished:
                        build_finished = True

                    if sync_finished and build_finished:
                        break

        if self.context.view_data.replace_target:
            pass

    def start_build(self, project_name):
        build_data = BuildData()
        build_data.build_editor = self.context.view_data.build_editor
        build_data.build_game = self.context.view_data.build_game
        build_data.ProjectPath = os.path.join(self.p4.ClientRoot, project_name)
        build_data.ProjectName = project_name
        build_data.EnginePath = os.path.join(self.p4.ClientRoot, "UE5EA")
        build_data.GameBuildConfig = self.context.view_data.GameConfig

        build_process = BuildProcess(build_data, self.context.event_queue)
        build_process.start()


class SyncProcess(Process):
    def __init__(self, sync_data: SyncData, event_queue):
        super().__init__()
        self.sync_data: SyncData = sync_data
        self.event_queue: Queue = event_queue

    def get_client_stream_param(self, relation_path):
        client_stream = self.sync_data.ClientStream
        if not client_stream.endswith("/"):
            client_stream += "/"
        if len(relation_path) > 0:
            client_stream += relation_path
        if relation_path[-1] == "/":
            client_stream += "..."

        changelist = "@" + self.sync_data.ChangeList
        client_stream += changelist
        return client_stream

    def get_total_sync_num(self, depot_path):
        cmd = 'p4 sync -N'

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

        self.event_queue.put(UIMessageData("added:{0}, updated:{1}, deleted:{2}".format(change_file_num[0],
                                                                                        change_file_num[1],
                                                                                        change_file_num[2])))
        return change_file_num[0] + change_file_num[1] + change_file_num[2]

    def read_sync_output(self, process):
        while process.poll() is None:
            output: str = process.stdout.readline().rstrip().decode('UTF8')
            if output == '' and process.poll() is not None:
                break
            if len(output) > 0:
                yield output

    def run(self):
        self.event_queue.put(UIMessageData("start sync source"))

        self.event_queue.put(EventData(EventEnum.BeginSyncSource))
        self.sync(self.sync_data.source_path)
        self.event_queue.put(EventData(EventEnum.SyncSourceFinished))

        self.event_queue.put(UIMessageData("start sync content"))
        self.sync(self.sync_data.content_path)

        self.event_queue.put(UIMessageData("finish sync content"))

        self.event_queue.put(EventData(EventEnum.SyncFinished))

    def sync(self, paths):
        depot_path = ""
        for x in paths:
            depot_path += self.get_client_stream_param(x)
            depot_path += " "
        source_sync_total = self.get_total_sync_num(depot_path)

        if source_sync_total > 0:
            cmd = 'p4 -I -C utf8 sync {0}'.format(depot_path)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
            process.daemon = True
            current = 0
            for output in self.read_sync_output(process):
                if "- updating" in output or "- added" in output or "- deleted" in output:
                    current += 1
                    self.event_queue.put(UISyncProgressData(current, source_sync_total))


class BuildProcess(Process):
    def __init__(self, build_data: BuildData, event_queue: Queue):
        super().__init__()
        self.build_data: BuildData = build_data
        self.event_queue: Queue = event_queue

    def run(self):
        if self.build_data.build_editor:
            self.build_editor()
        if self.build_data.build_game:
            self.build_game()

        self.event_queue.put(EventData(EventEnum.BuildFinished))

    def build_editor(self):
        self.event_queue.put(UIMessageData("Start Build Editor"))
        project_file = os.path.join(self.build_data.ProjectPath, "{0}.uproject".format(self.build_data.ProjectName))

        def generate_project_files():

            engine_batch = os.path.join(self.build_data.EnginePath, "Engine", "Build", "BatchFiles",
                                        "GenerateProjectFiles.bat")

            if os.path.exists(engine_batch):
                cmd = [engine_batch, project_file, "-VisualStudio2022", "-Game", "-Engine", "-Programs"]
                p = subprocess.Popen(cmd, shell=True, stdout=None, encoding="UTF8")
                p.communicate()

        generate_project_files()

        bat = "{0}/Engine/Build/BatchFiles/Build.bat".format(self.build_data.EnginePath)
        params = " -Target={0}Editor Win64 {1}".format(self.build_data.ProjectName, "Development")
        params += " -Project={0}".format(project_file)
        params += ' -Target="ShaderCompileWorker Win64 Development -Quiet"'
        params += " -WaitMutex -FromMsBuild"

        process = subprocess.Popen("{0} {1}".format(bat, params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        process.daemon = True

        while process.poll() is None:
            try:
                output: str = process.stdout.readline().rstrip().decode('UTF8')
                if output == '' and process.poll() is not None:
                    break

                if len(output) > 0:
                    self.update_build_progress(output)
                    print(output)

            except:
                pass

    def build_game(self):

        self.event_queue.put(UIMessageData("start build game"))
        UAT_Path = os.path.join(self.build_data.EnginePath, "Engine", "Build", "BatchFiles",
                                "RunUAT.bat")

        CMD_Params = "BuildCookRun -project={0}/{1}.uproject -platform=Win64 -target={1} -clientconfig={2}".format(
            self.build_data.ProjectPath, self.build_data.ProjectName, self.build_data.GameBuildConfig)

        CMD_Params += " -noP4 -stdout -UTF8Output -Build -SkipCook -SkipStage -SkipPackage"
        CMD_Params += " -skipbuildeditor -nobootstrapexe"

        process = subprocess.Popen("{0} {1}".format(UAT_Path, CMD_Params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        while process.poll() is None:
            output = process.stdout.readline().rstrip().decode('UTF8', errors='ignore')
            if output == '' and process.poll() is not None:
                break
            if len(output) > 0:
                self.update_build_progress(output)
                print(output)

        self.event_queue.put(UIMessageData("finish build game"))

    def update_build_progress(self, output):
        if output.startswith('['):
            word = output[1:output.index("]", 1)]
            word = word.split("/")
            if len(word) == 2:
                a = int(word[0])
                b = int(word[1])
                if b > 0:
                    self.event_queue.put(UIBuildProgressData(a, b))
                else:
                    print(output)


def main():
    context = BuildContext()
    view = MainView(context)
    view.mainloop()


if __name__ == "__main__":
    main()

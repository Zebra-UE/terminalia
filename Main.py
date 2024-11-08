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
import selectors
from multiprocessing import Process, Queue


class BuildStep(Enum):
    Undefined = 0
    Ready = 1
    Sync_Source = 2
    Build_Editor = 3
    GenerateProjectFiles = 4
    Build_Game = 5
    Replace_Target = 6
    Start_Game = 7
    Sync_Content = 8

    Finished = 100


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
        self.EnginePath = ""
        self.ProjectPath = ""
        self.ProjectName = ""
        self.BuildConfig = ""

class UIMessage:
    def __init__(self,step,current,total):
        self.step: BuildStep = step
        self.current = current
        self.total = total

class BuildTask(Process):
    def __init__(self):
        super().__init__(self)
    def update_build_progress(self,output):
        if output.startswith('['):
            word = output[1:output.index("]", 1)]
            word = word.split("/")
            if len(word) == 2:
                print(output)
                a = int(word[0])
                b = int(word[1])
                if b > 0:
                    return a,b
        return 0,1


class BuildEditorTask(BuildTask):
    def __init__(self,request:BuildEditorRequest,message_queue):
        super().__init__(self)
        self.message_queue:Queue = message_queue
        self.request:BuildEditorRequest = request
    def run(self):
        self.message_queue.put(UIMessage(BuildStep.GenerateProjectFiles,0,0))
        project_file = os.path.join(self.request.ProjectPath, self.request.ProjectName,
                                    "{0}.uproject".format(self.request.ProjectName))


        def generate_project_files():

            engine_batch = os.path.join(self.request.EnginePath, "Engine", "Build", "BatchFiles",
                                        "GenerateProjectFiles.bat")

            if os.path.exists(engine_batch):
                cmd = [engine_batch, project_file, "-VisualStudio2022", "-Game", "-Engine", "-Programs"]
                p = subprocess.Popen(cmd, shell=True, stdout=None, encoding="UTF8")
                p.communicate()

        self.message_queue.put(UIMessage(BuildStep.GenerateProjectFiles, 0, 1))
        generate_project_files()
        self.message_queue.put(UIMessage(BuildStep.GenerateProjectFiles, 1, 1))
        self.message_queue.put(UIMessage(BuildStep.GenerateProjectFiles, 0, -1))

        bat = "{0}/Engine/Build/BatchFiles/Build.bat".format(self.request.EnginePath)
        params = " -Target={0}Editor Win64 {1}".format(self.request.ProjectName, self.request.BuildConfig)
        params += " -Project={0}".format(project_file)
        params += ' -Target="ShaderCompileWorker Win64 Development -Quiet"'
        params += " -WaitMutex -FromMsBuild"

        self.message_queue.put(UIMessage(BuildStep.Build_Editor, 0, 1))

        process = subprocess.Popen("{0} {1}".format(bat, params), shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        process.daemon = True
        while process.poll() is None:
            try:
                output: str = process.stdout.readline().rstrip().decode('UTF8')
                if output == '' and process.poll() is not None:
                    break
                # ------ Building 3 action(s) started ------
                #
                if len(output) > 0:
                    current,total = self.update_build_progress(output)
                    self.message_queue.put(UIMessage(BuildStep.Build_Editor, current, total))
            except:
                pass

class BuildGameRequest:
    def __init__(self):
        self.ClientRoot = ""
        self.EnginePathName = ""
        self.ProjectName = ""
        self.BuildConfig = ""
class BuildGameResponse:
    def __init__(self):
        self.success: bool = False
        self.target_path = ""

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
        self.build_system = None
        self.ui_tread = None

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

    def switch_start_game_checkbox(self):
        if self.tk_start_game.get():
            self.left_tree.expand(6)
        else:
            self.left_tree.collect(6)

    def step(self):
        self.build_data.sync = self.tk_sync.get()

        if self.build_data.sync:
            changelist = self.tk_change_list.get()
            if len(changelist) == 0:
                changelist = self.get_latest_changelist()
            self.build_data.ChangeList = changelist
        else:
            p = os.path.join(self.build_data.ClientRoot, "changelist.txt")
            with open(p, "r", encoding="utf8") as f:
                changelist = f.readline()
                changelist = changelist.strip()
                self.build_data.ChangeList = changelist

        self.view_data.event_data.info("changelist: " + self.build_data.ChangeList)

        self.build_data.build_editor = self.tk_build_editor.get()
        self.build_data.build_game = self.tk_build_exe.get()
        self.build_data.GameConfig = self.tk_game_config_combobox.get()

        #
        project_path = os.path.join(self.build_data.ClientRoot, "S1Game")
        for f in os.listdir(project_path):
            if f.endswith(".uproject"):
                self.build_data.ProjectName = f[:-9]

        self.build_data.replace_target = self.tk_replace.get()
        self.build_data.start_game = self.tk_start_game.get()
        self.build_data.enable_trace = self.tk_start_game_trace.get()
        self.build_data.additive_game_param = self.tk_start_game_command.get()
        self.build_data.start_server = self.tk_start_server.get()

    def get_latest_changelist(self):
        # p4 changes -m 1 -s submitted
        output = subprocess.check_output("p4 changes -m 1 -s submitted", encoding='utf-8', errors='ignore')
        output = output.strip()
        # Change 155713 on 2024/10/10
        output = output.split()
        if output[0] == 'Change':
            return output[1]

        raise Exception("change fail")

    def run(self):
        if self.build_system is not None:
            return

        self.view_data.event_data.clean()
        self.tk_event_listview.delete(0, tk.END)

        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        self.view_data.event_data.info("begin {0}".format(time_str))

        self.view_data.step = BuildStep.Ready
        self.save_setting()

        self.init_p4()
        self.step()

        self.build_system = BuildSystem(self.build_data, self.view_data)
        self.build_system.daemon = True
        self.build_system.start()

        self.ui_tread = UIThread(self.build_data, self)
        self.ui_tread.daemon = True
        self.ui_tread.start()

    def finished(self):
        if self.build_system is not None:
            self.build_system = None

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

    def refresh_event(self):
        for x in self.view_data.event_data:
            self.tk_event_listview.insert(tk.END, x)


class UIThread(threading.Thread):
    def __init__(self, build_data, view):
        threading.Thread.__init__(self)
        self.build_data: BuildData = build_data
        self.view: MainView = view
        self.view_data = self.view.view_data
        self.step_text = ""
        self.dot_time = 0
        self.dot_text = ""

        self.is_finished = False

        self.step = BuildStep.Undefined
        self.progress_value: float = 0.0

    def run(self):

        while not self.is_finished:
            self.tick()
            self.view.update()
            time.sleep(0.02)

    def tick(self):
        if self.view_data.step != self.step:
            self.step = self.view_data.step
            self.on_build_step_change()

        self.view.refresh_event()

        if self.step == BuildStep.Finished:
            self.is_finished = True
            self.view.finished()
            self.view.tk_step_text.set(self.step_text)
        elif self.step != BuildStep.Ready:
            self.update_progress()

    def on_build_step_change(self):
        if self.step == BuildStep.Sync_Source:
            self.step_text = "1. sync source"
        elif self.step == BuildStep.Build_Editor:
            self.step_text = "2. build editor"
        elif self.step == BuildStep.Build_Game:
            self.step_text = "3. build game"
        elif self.step == BuildStep.Sync_Content:
            self.step_text = "4. sync content"
        elif self.step == BuildStep.Finished:
            self.step_text = "finished"

        self.view.progress_bar.step(0 - self.progress_value)
        self.progress_value = 0

    def update_progress(self):

        current_progress_value = self.view_data.progress_value.get()
        delta = current_progress_value - self.progress_value
        self.view.progress_bar.step(delta)
        self.progress_value = current_progress_value

        if time.time() - self.dot_time > 0.5:
            self.dot_text += "."
            if len(self.dot_text) >= 6:
                self.dot_text = "."
            self.dot_time = time.time()

        self.view.tk_step_text.set(self.step_text + self.dot_text)
        self.view.tk_progress_text.set(
            "{0}/{1}".format(self.view_data.progress_value.current, self.view_data.progress_value.total))


class BuildSystem(threading.Thread):
    def __init__(self, build_data: BuildData, view_data: ViewData):
        threading.Thread.__init__(self)
        self.build_data = build_data
        self.view_data = view_data
        self.target_path = None

    def run(self):
        self.view_data.step = BuildStep.Ready

        sync_content_process = None
        if self.build_data.sync:
            request = SyncRequest()
            request.add_path("UE5EA/")
            request.add_path("{0}/Source/".format("S1Game"))
            request.add_path("{0}/Plugins/".format("S1Game"))
            request.add_path(
                "{0}/{1}.uproject".format("S1Game", self.build_data.ProjectName))

            self.sync_source(request)

            request = SyncRequest()

            request.add_path("{0}/Content/".format("S1Game"))
            request.add_path("{0}/Config/".format("S1Game"))
            request.add_path("{0}/Scripts/".format("S1Game"))
            request.add_path("{0}/Build/".format("S1Game"))
            request.add_path("S1GameServer")
            sync_content_process = self.sync_content(request)

            self.sync_save()

        if self.build_data.build_editor:

            self.build_editor()

        if self.build_data.build_game:
            request = BuildGameRequest()
            request.ClientRoot = self.build_data.ClientRoot
            request.BuildConfig = self.build_data.GameConfig
            request.EnginePathName = "UE5EA"
            request.ProjectName = self.build_data.ProjectName
            rsp = self.build_game(request)
            if not rsp.success:
                self.view_data.event_data.info("finished")
                self.view_data.step = BuildStep.Finished
                return


        self.build_data.target_path = self.find_target()
        if self.build_data.replace_target:
            q = ReplaceTargetRequest()

            self.replace_target(q)
        if self.build_data.start_game:
            self.start_game()
        if self.build_data.start_server:
            self.start_server()

        if self.build_data.sync and sync_content_process is not None:
            self.view_data.step = BuildStep.Sync_Content
            while sync_content_process.poll() is None:
                output = sync_content_process.stdout.readline().rstrip().decode('utf-8', errors='ignore')
                if output == '' and sync_content_process.poll() is not None:
                    break
                if len(output) > 0:
                    print(output)

        self.view_data.event_data.info("finished")

        self.view_data.step = BuildStep.Finished

    def sync_content(self, request: SyncRequest):
        cmd = 'p4 -I -C utf8 sync '
        for x in request.path:
            cmd += self.get_client_stream_param(x)
            cmd += " "

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        process.daemon = True
        return process

    def sync_source(self, request: SyncRequest):

        self.view_data.step = BuildStep.Sync_Source
        self.build_data.progress_value = ProgressValue(0, 1)

        cmd = 'p4 sync -N'
        depot_path = ""
        for x in request.path:
            depot_path += self.get_client_stream_param(x)
            depot_path += " "

        output: str = subprocess.check_output(cmd + " " + depot_path, encoding='utf-8')
        self.build_data.progress_value.step(1)
        change_file_num = [0, 0, 0]
        if output.startswith("Server network estimates:"):
            output = output[len("Server network estimates: "):]
            l = output.split(",")
            x = l[0][len("files added/updated/deleted="):]
            x = x.split("/")
            self.view_data.event_data.info("add:{0},updated:{1},deleted:{2}".format(x[0], x[1], x[2]))
            for i in range(3):
                change_file_num[i] = int(x[i])
        else:
            raise Exception("Server network estimates not yet implemented")

        self.build_data.progress_value.set(0, change_file_num[0] + change_file_num[1] + change_file_num[2])

        cmd = 'p4 -I -C utf8 sync {0}'.format(depot_path)

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        process.daemon = True

        for line in self.read_process_output(process):
            self.update_sync_progress(line)

    def sync_save(self):
        changelist_txt = os.path.join(self.build_data.ClientRoot, "changelist.txt")
        if os.path.exists(changelist_txt):
            os.remove(changelist_txt)
        with open(changelist_txt, mode="w", encoding='utf8') as f:
            f.write(self.build_data.ChangeList)

    def build_game(self, request: BuildGameRequest):
        response = BuildGameResponse()
        self.view_data.step = BuildStep.Build_Game
        self.build_data.progress_value = ProgressValue(0, 0)

        UAT_Path = os.path.join(self.build_data.ClientRoot, request.EnginePathName, "Engine", "Build", "BatchFiles",
                                "RunUAT.bat")

        CMD_Params = "BuildCookRun -project={0}/{1}/{1}.uproject -platform=Win64 -target={1} -clientconfig={2}".format(
            self.build_data.ClientRoot, request.ProjectName, request.BuildConfig)

        CMD_Params += " -noP4 -stdout -UTF8Output -Build -SkipCook -SkipStage -SkipPackage"
        CMD_Params += " -skipbuildeditor -nobootstrapexe"

        game_path = os.path.join(self.build_data.ClientRoot, "S1Game", "Binaries", "Win64",
                                 self.get_build_output_name())
        if os.path.exists(game_path):
            self.view_data.event_data.info("remove {0}".format(game_path))
            os.remove(game_path)

        self.view_data.event_data.info("build game Win64 {0}".format(self.build_data.GameConfig))

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
                    self.view_data.event_data.error(output)
                    error_text.append(output)
            time.sleep(0.01)

        time.sleep(2.0)
        if not os.path.exists(game_path):
            for x in error_text:
                print(x)
            self.view_data.event_data.error("{0} is not exists".format(game_path))
            response.success = False
        else:
            response.target_path = game_path
            response.success = True

        return response

    def update_build_progress(self, output):
        if output.startswith('['):
            word = output[1:output.index("]", 1)]
            word = word.split("/")
            if len(word) == 2:
                print(output)
                a = int(word[0])
                b = int(word[1])
                if b > 0:
                    self.view_data.progress_value.set(a, b)

    def update_sync_progress(self, output):
        if "- updating" in output:
            self.view_data.progress_value.step(1)
        elif "- added as" in output:
            self.view_data.progress_value.step(1)
        elif "- deleted as" in output:
            self.view_data.progress_value.step(1)

    def read_process_output(self, process):
        while process.poll() is None:
            output: str = process.stdout.readline().rstrip().decode('UTF8')
            if output == '' and process.poll() is not None:
                break
            if len(output) > 0:
                yield output
            time.sleep(0.1)

    def build_editor(self):
        request = BuildEditorRequest()
        request.EnginePathName = "UE5EA"
        request.ProjectName = self.build_data.ProjectName
        request.BuildConfig = "Development"

        p = BuildEditorTask(request)
        p.start()


    def get_build_output_name(self, ext="exe"):
        if self.build_data.GameConfig == "Development":
            return "{0}.{1}".format(self.build_data.ProjectName, ext)
        else:
            return "{0}-Win64-{1}.{2}".format(self.build_data.ProjectName, self.build_data.GameConfig, ext)

    def find_target(self):
        if self.target_path is None:
            for k in os.listdir(self.build_data.TargetPath):
                if "_{0}_".format(self.build_data.ChangeList) in k:
                    p = os.path.join(self.build_data.TargetPath, k)
                    if not os.path.isdir(p):
                        continue
                    else:
                        self.target_path = (
                            os.path.join(p, "Win64", "S1Game", "Binaries", "Win64", self.get_build_output_name()))
                        break
        return self.target_path

    def replace_target(self,request:ReplaceTargetRequest):
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

def main():
    view = MainView()

if __name__ == "__main__":
    main()

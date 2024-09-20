import threading
import tkinter as tk
import subprocess
import os
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
        self.ClientStream = ""
        self.step = 0
        self.sync_progress = 0


class MainView(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)

        self.build_setting = BuildSetting()
        self.build_data = BuildData()

        self.tk_P4PORT = tk.StringVar()
        self.tk_P4USER = tk.StringVar()
        self.tk_P4CLIENT = tk.StringVar()
        self.tk_sync = tk.IntVar()
        self.tk_build_editor = tk.IntVar()
        self.tk_build_exe = tk.IntVar()
        self.tk_change_list = tk.StringVar()
        self.sync_progress = None

        self.work_thread = None
        self.create_view()

    def create_view(self):

        setting_saver_file = SettingSaver()
        setting_saver = setting_saver_file.load()
        self.tk_P4PORT.set(setting_saver.P4PORT)
        self.tk_P4USER.set(setting_saver.P4USER)
        self.tk_P4CLIENT.set(setting_saver.P4CLIENT)

        self.build_setting.P4PORT = setting_saver.P4PORT
        self.build_setting.P4USER = setting_saver.P4USER
        self.build_setting.P4CLIENT = setting_saver.P4CLIENT

        a = tk.Label(self, text='Server', font=('Arial', 10))
        a.place(x=10, y=10)
        b = tk.Entry(self, show=None, font=('Arial', 10), textvariable=self.tk_P4PORT)
        b.place(x=100, y=10, width=300)
        c = tk.Label(self, text='User', font=('Arial', 10))
        c.place(x=10, y=40)
        d = tk.Entry(self, show=None, font=('Arial', 10), textvariable=self.tk_P4USER)
        d.place(x=100, y=40)
        e = tk.Label(self, text='Workspace', font=('Arial', 10))
        e.place(x=10, y=70)
        f = tk.Entry(self, show=None, font=('Arial', 10), textvariable=self.tk_P4CLIENT)
        f.place(x=100, y=70)

        tk.Checkbutton(self, text="1. sync", variable=self.tk_sync).place(x=10, y=130)
        tk.Label(self, text='change').place(x=90, y=130)
        self.sync_progress = ttk.Progressbar(self)
        self.sync_progress.place(x=360, y=130, width=100, height=10)

        tk.Entry(self, textvariable=self.tk_change_list).place(x=150, y=130, width=180)
        tk.Checkbutton(self, text="2. build editor", variable=self.tk_build_editor).place(x=10, y=150)
        tk.Checkbutton(self, text="3. build game", variable=self.tk_build_exe).place(x=10, y=170)

        b = tk.Button(self, text='Build', font=('Arial', 10), width=10, height=1,
                      command=lambda: self.run())
        b.place(x=350, y=240)
        self.schedule_tick()
        self.mainloop()

    def schedule_tick(self):
        self.tick()
        self.after(100, lambda: self.schedule_tick())

    def tick(self):
        if self.build_data.step == 1:
            self.sync_progress.step(self.build_data.sync_progress)

            self.update()

    def run(self):
        self.save_setting()
        self.init_p4()

        t = BuildSystem(self.build_data)
        t.daemon = True
        t.start()

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

    def run(self):
        while self.build_data.step != -1:
            pass

    def sync(self):

        subprocess.run('p4 -C utf8 sync --parallel=threads=24 {0}/...{1} '.format(stream, changelist), cwd=cwd,
                       stdout=None)
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

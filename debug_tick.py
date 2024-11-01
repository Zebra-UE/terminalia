import datetime
import time
import os

frame_num = 0
all_frame_time = dict()
g_count = 0

with open(r"D:\Game\S1Game_trunk_0.165734.165734.165734_165734_Development_Win64_Timer\Win64\S1Game\Saved\Logs\S1Game.log",mode="r",encoding="utf8") as f:
    frame_start_time = 0
    current_frame_num = -1
    frame_begin_map = -1
    frame_end_map = 0
    for line in f.readlines():
        line = line.strip()
        if len(line) == 0:
            continue
        if line[0] != '[':
            continue
        x = line.index(']')
        if x < 0:
            continue
        if line[x+1] != '[':
            continue
        y = line.index(']',x + 1)
        if y < 0:
            continue



        line_frame_num = int(line[x + 2:y].strip())

        if "Warning: CallOnShow:1505" in line:
            frame_begin_map = line_frame_num
            print("onshow:",line_frame_num)

        elif "LogBirthland: StopLoadingScreen" in line:
            frame_end_map = line_frame_num + 10
            print("stop show",frame_end_map)

        if "FlushAsyncLoading" in line:
            print(line)

        t = datetime.datetime.strptime(line[1:x], "%Y.%m.%d-%H.%M.%S:%f")

        if line_frame_num == 0 and current_frame_num == -1:
            current_frame_num = 0
            frame_start_time = t
        else:
            if current_frame_num + 1 == line_frame_num:
                delta = t - frame_start_time
                delta = delta.total_seconds() * 1000

                if delta > 10:
                    print("[{0}]{1}".format(current_frame_num, delta))

                current_frame_num = line_frame_num
                frame_start_time = t
            elif current_frame_num == line_frame_num:
                continue
            else:
                current_frame_num = line_frame_num
                frame_start_time = t




import array
import math
import os
import threading
import time
import wave
from multiprocessing.context import Process
from typing import List

import keyboard as keyboard
import matplotlib.pyplot as plt
import numpy
import pywt
import simpleaudio
from numpy.typing.tests.data.fail import ndarray
from pydub import AudioSegment
from pydub.playback import play
from scipy import signal

default_window_length = 3


class PlayMusicThread(threading.Thread):

    def __init__(self, name, filename):
        threading.Thread.__init__(self)
        self.name = name
        self.filename = filename
        self._stop_event = threading.Event()

    def run(self):
        print("start thread：" + self.name)
        self._play_music()
        print("exit thread：" + self.name)

    def _play_music(self):
        print("play music in " + self.name)
        sound = AudioSegment.from_wav(self.filename)
        play(sound)

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


def _read_wav(filename: str):
    # open file, get metadata for audio
    try:
        wf = wave.open(filename, "rb")
    except IOError as e:
        print(e)
        return

    # typ = choose_type( wf.getsampwidth() ) # TODO: implement choose_type
    nsamps = wf.getnframes()
    assert nsamps > 0

    fs = wf.getframerate()
    assert fs > 0

    # Read entire file and make into an array
    samps = list(array.array("i", wf.readframes(nsamps)))

    try:
        assert nsamps == len(samps)
    except AssertionError:
        print(nsamps, "not equal to", len(samps))

    return samps, fs


# print an error when no data can be found
def _no_audio_data():
    print("No audio data for sample, skipping...")
    return None, None


# simple peak detection
def _peak_detect(data):
    max_val = numpy.amax(abs(data))
    peak_ndx = numpy.where(data == max_val)
    if len(peak_ndx[0]) == 0:  # if nothing found then the max must be negative
        peak_ndx = numpy.where(data == -max_val)
    return peak_ndx


def _bpm_detector(data, fs):
    cA = []
    cD_sum = []
    levels = 4
    max_decimation = 2 ** (levels - 1)
    min_ndx = math.floor(60.0 / 220 * (fs / max_decimation))
    max_ndx = math.floor(60.0 / 40 * (fs / max_decimation))

    for loop in range(0, levels):
        # 1) DWT
        if loop == 0:
            [cA, cD] = pywt.dwt(data, "db4")
            cD_minlen = len(cD) / max_decimation + 1
            cD_sum = numpy.zeros(math.floor(cD_minlen))
        else:
            [cA, cD] = pywt.dwt(cA, "db4")

        # 2) Filter
        cD = signal.lfilter([0.01], [1 - 0.99], cD)

        # 4) Subtract out the mean.

        # 5) Decimate for reconstruction later.
        cD = abs(cD[::(2 ** (levels - loop - 1))])
        cD = cD - numpy.mean(cD)

        # 6) Recombine the signal before ACF
        #    Essentially, each level the detail coefs (i.e. the HPF values) are concatenated to the beginning of the array
        cD_sum = cD[0:math.floor(cD_minlen)] + cD_sum

    if [b for b in cA if b != 0.0] == []:
        return _no_audio_data()

    # Adding in the approximate data as well...
    cA = signal.lfilter([0.01], [1 - 0.99], cA)
    cA = abs(cA)
    cA = cA - numpy.mean(cA)
    cD_sum = cA[0:math.floor(cD_minlen)] + cD_sum

    # ACF
    correl = numpy.correlate(cD_sum, cD_sum, "full")

    midpoint = math.floor(len(correl) / 2)
    correl_midpoint_tmp = correl[midpoint:]
    peak_ndx = _peak_detect(correl_midpoint_tmp[min_ndx:max_ndx])
    if len(peak_ndx) > 1:
        return _no_audio_data()

    peak_ndx_adjusted = peak_ndx[0] + min_ndx
    bpm = 60.0 / peak_ndx_adjusted * (fs / max_decimation)
    return bpm, correl


def get_bpm_array(filename: str,
    window: int = default_window_length) -> ndarray:
    samps, fs = _read_wav(filename)
    n = 0
    nsamps = len(samps)
    window_samps = int(window * fs)
    samps_ndx = 0  # First sample in window_ndx
    max_window_ndx = math.floor(nsamps / window_samps)
    bpms = numpy.zeros(max_window_ndx)

    # Iterate through all windows
    for window_ndx in range(0, max_window_ndx):

        # Get a new set of samples
        # print(n,":",len(bpms),":",max_window_ndx_int,":",fs,":",nsamps,":",samps_ndx)
        data = samps[samps_ndx:samps_ndx + window_samps]
        if not ((len(data) % window_samps) == 0):
            raise AssertionError(str(len(data)))

        bpm, correl_temp = _bpm_detector(data, fs)
        if bpm is None:
            continue
        bpms[window_ndx] = bpm

        # Iterate at the end of the loop
        samps_ndx = samps_ndx + window_samps

        # Counter for debug...
        n = n + 1

    bpm = numpy.median(bpms)
    print("Completed!  Estimated Beats Per Minute:", bpm)
    return bpms


def transform_audio_file(filename: str):
    file_name = os.path.splitext(filename)[0]
    file_type = os.path.splitext(filename)[-1]
    wav_file_name = file_name + '.wav'

    if file_type == '.mp3':
        sound = AudioSegment.from_mp3(filename)
    elif file_type == '.flv':
        sound = AudioSegment.from_flv(filename)
    elif file_type == '.ogg':
        sound = AudioSegment.from_ogg(filename)
    elif file_type == '.raw':
        sound = AudioSegment.from_raw(filename)
    elif file_type == '.wav':
        print("The audio file is 'wav', it need not to transform.")
        return wav_file_name
    else:
        raise AssertionError("The file type is not supported.")

    sound.export(wav_file_name, format='wav')

    return wav_file_name


def play_music(filename: str):
    seg = AudioSegment.from_wav(filename)

    playback = simpleaudio.play_buffer(
        seg.raw_data,
        num_channels=seg.channels,
        bytes_per_sample=seg.sample_width,
        sample_rate=seg.frame_rate
    )

    try:
        print("play music....")
        playback.wait_done()
    except KeyboardInterrupt:
        playback.stop()


def play_music_and_get_time(filename: str) -> Process:
    import multiprocessing
    proc = multiprocessing.Process(target=play_music, args=(filename,))
    proc.start()

    return proc


def record_keyboard(
    window_count: int,
    window: int = default_window_length
) -> List[float]:
    records = []
    start_at = time.time()
    window_records = [0 for _ in range(window_count)]

    def record_pressed_key(e):
        records.append(time.time())

    keyboard.hook(record_pressed_key)
    keyboard.wait('esc')

    for record in records:
        index = round(math.ceil(max(record - start_at, 0) / window))
        if index <= window_count:
            window_records[index] += 1

    return window_records


if __name__ == "__main__":
    wav_filename = transform_audio_file('song.mp3')
    bpms = get_bpm_array(wav_filename)
    music_proc = play_music_and_get_time(wav_filename)
    keyboard_window_records = record_keyboard(len(bpms))

    music_proc.terminate()

    plot_x = list(
        range(0,
              len(bpms) * default_window_length, default_window_length))
    plt.xlabel('time (s)')
    plt.plot(plot_x, bpms, "x-", label="BPM")
    plt.plot(plot_x, keyboard_window_records, "+-", label="Keypass")
    plt.grid(True)
    plt.legend(bbox_to_anchor=(1.0, 1), loc=1, borderaxespad=0.)
    plt.show(block=True)

import csv
import hashlib
import math
import subprocess
from typing import List

# [1, 1/2, 1/4, 1/8, 1/16]
import mido

DEFAULT_LEVEL_LENGTH = 5
DEFAULT_NOTE_LENGTH = 7
DEFAULT_FILE_NAME = 'love_song'
note_beta_dens = [16, 8, 4, 2, 1]


def read_csv_file() -> List[List[str]]:
    with open('data.csv', newline='') as f:
        spam_reader = csv.reader(f, delimiter=',')
        records = [row for row in spam_reader]
        return records[1:]


def date_hash(date: str, time: str) -> int:
    encode_str = date + ' ' + time
    sha_code = hashlib.sha256(encode_str.encode('utf-8')).hexdigest()
    count = 0
    for char in sha_code:
        count += ord(char)
    return count % 8


def get_level_number(duration: int, level_list: List[int]) -> float:
    note_beta_index = DEFAULT_LEVEL_LENGTH - 1
    for i in range(0, DEFAULT_LEVEL_LENGTH - 1):
        if level_list[i] > duration:
            note_beta_index = i - 1
            break
    return 1 / note_beta_dens[note_beta_index]


def generate_level(duration_list: List[int]) -> List[int]:
    level_list = []
    max_v = max(duration_list)
    min_v = min(duration_list)
    delta = round((max_v - min_v) / 5)
    sum = 0
    for i in range(0, DEFAULT_LEVEL_LENGTH - 1):
        level_list.append(sum)
        sum += delta

    return level_list


def make_song(records: List[List[str]]):
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
    track.append(mido.MetaMessage('track_name', name='Choir', time=0))
    track.append(mido.Message('program_change', program=54, time=0))

    record_length = len(records)
    bar_count = round(math.floor(record_length / 7)) + 1

    # Set the basic pitch is Middle C, the value is 60.
    pitch_list = [date_hash(item[0], item[1]) + 60 for item in records]
    duration_list = [int(item[2]) for item in records]
    level_list = generate_level(duration_list)
    note_beta_list = [get_level_number(dur, level_list) for dur in
                      duration_list]

    index = 0
    for i in range(bar_count - 1):
        for note in range(DEFAULT_NOTE_LENGTH):
            pitch = 0 if index >= len(pitch_list) else pitch_list[index]
            note_time = 1 if index >= len(pitch_list) else note_beta_list[index]

            track.append(
                mido.Message('note_on',
                             note=pitch,
                             velocity=96,
                             time=round(480 * note_time))
            )
            track.append(
                mido.Message('note_off',
                             note=pitch_list[index],
                             velocity=96,
                             time=round(480 * (1 - note_time)))
            )
            index += 1

    mid.save(DEFAULT_FILE_NAME + '.mid')
    print('Make a new song!')


def transform_file():
    subprocess.call(['fluidsynth',
                     '-ni', 'FluidR3Mono_GM.sf3',
                     DEFAULT_FILE_NAME + '.mid',
                     '-F', DEFAULT_FILE_NAME + '.wav',
                     '-r', '44100'])
    print('Transform mid file to wav file.')


if __name__ == "__main__":
    records = read_csv_file()
    make_song(records)
    transform_file()

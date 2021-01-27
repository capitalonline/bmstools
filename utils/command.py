import os
import shutil


def file_exists(file_path):
    if os.path.exists(file_path):
        return True
    return False


def remove_tree(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        if os.path.isfile(path):
            os.remove(path)
    except OSError as e:
        return e

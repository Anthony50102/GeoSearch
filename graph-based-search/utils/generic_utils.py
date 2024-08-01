import yaml
import shlex
import subprocess
import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

def create_directory(path, recursive=False, use_sudo=False):
    try:
        if recursive:
            os.makedirs(path, exist_ok=True)
        else:
            os.mkdir(path)
        print(f"Directory '{path}' created successfully.")
    except PermissionError:
        if use_sudo:
            try:
                if recursive:
                    subprocess.run(['sudo', 'mkdir', '-p', path], check=True)
                else:
                    subprocess.run(['sudo', 'mkdir', path], check=True)
                print(f"Directory '{path}' created successfully with elevated permissions.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to create directory '{path}' with elevated permissions: {e}")
        else:
            print(f"Permission denied: could not create directory '{path}'")
    except Exception as e:
        print(f"An error occurred: {e}")
    
def shell_rmtree(path):
    """
    Recursively delete a directory tree using shell commands.

    :param path: Path to the directory to be removed.
    """
    try:
        # Use the 'rm -rf' command to remove the directory tree
        subprocess.check_call(['sudo','rm', '-rf', path])
    except subprocess.CalledProcessError as e:
        print(f"Error removing directory {path}: {e}")

def tile(x, count, dim=0):
    """
    Tiles x on dimension dim count times.
    """
    perm = list(range(len(x.size())))
    if dim != 0:
        perm[0], perm[dim] = perm[dim], perm[0]
        x = x.permute(perm).contiguous()
    out_size = list(x.size())
    out_size[0] *= count
    batch = x.size(0)
    x = x.view(batch, -1) \
         .transpose(0, 1) \
         .repeat(count, 1) \
         .transpose(0, 1) \
         .contiguous() \
         .view(*out_size)
    if dim != 0:
        x = x.permute(perm).contiguous()
    return x


def to_cuda(x, device=None):
    if device:
        x = x.to(device)
    return x


def create_mask(x, N, device=None):
    x = x.data
    mask = np.zeros((x.size(0), N))
    for i in range(x.size(0)):
        mask[i, :x[i]] = 1
    return to_cuda(torch.Tensor(mask), device)


def get_config(config_path="config.yml"):
    with open(config_path, "r") as setting:
        config = yaml.load(setting)
    return config

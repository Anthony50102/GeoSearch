#!/bin/bash

# Check if the directory is provided as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <directory>"
  exit 1
fi

TARGET_DIR=$1

# Check if the provided argument is a directory
if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: $TARGET_DIR is not a directory"
  exit 1
fi

# Change permissions to 777 for all files and directories recursively
chmod -R 777 "$TARGET_DIR"

echo "Permissions for all files and directories within $TARGET_DIR have been set to 777."

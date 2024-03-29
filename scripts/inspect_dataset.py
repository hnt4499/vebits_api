import os
import argparse
import sys
from shutil import copy

import pandas as pd
import numpy as np
import cv2

from vebits_api import others_util, bbox_util, vis_util, labelmap_util

DESCRIPTION = """This script loads in a csv file containing dataset data. List
of images will be then generated. Images will be loaded one by one, visualized
and displayed on the screen. Use `a` and `d` to move backwards and forwards,
respectively, `w` to copy displaying image to specified folder and `q` to quit.
"""


def main(args):
    # Read csv and generate image list
    df = pd.read_csv(args.csv_path)
    img_list = df.filename.unique()
    num_imgs = len(img_list)
    # Read arguments
    index = args.start
    dataset_dir = args.dataset_dir
    incorrect_dir = args.incorrect_dir
    labelmap_dict = labelmap_util.get_label_map_dict(args.labelmap_path)
    # Initialize displaying window
    cv2.namedWindow('Inspecting Dataset', cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Inspecting Dataset", 800, 800)
    # Start inspecting
    while True:
        img_name = img_list[index]
        img_path = os.path.join(dataset_dir, img_name)

        if not os.path.isfile(img_path):
            print(">>> File not found: {}".format(img_path))
            index = (index + 1) % num_imgs
            continue
        # Load image and visualize
        img = cv2.imread(img_path)
        bboxes, classes = bbox_util.get_bboxes_array_and_class(df, img_name)
        vis_util.draw_boxes_on_image(img, bboxes, classes, labelmap_dict)
        vis_util.draw_number(img, index)
        cv2.imshow("Inspecting Dataset", img)
        # Handle keystroke
        key = cv2.waitKey(0)
        if key == ord("d"):
            index = (index + 1) % num_imgs
        elif key == ord("a"):
            index = (index - 1) % num_imgs
        elif key == ord("w"):
            index = (index + 1) % num_imgs
            copy(img_path, os.path.join(incorrect_dir, img_name))
        elif key == ord("q"):
            print(">>> Current index: {}".format(index))
            break


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=DESCRIPTION)

    parser.add_argument('dataset_dir', type=str,
        help='Directory to the dataset.')
    parser.add_argument('csv_path', type=str,
        help='Path to the csv file.')
    parser.add_argument('labelmap_path', type=str,
        help='Path to the labelmap.')
    parser.add_argument('incorrect_dir', type=str,
        help='Directory to which all the incorrectly \
        labelled images will be saved.')
    parser.add_argument('--start', type=int, default=0,
        help='Starting point. Default=0 (i.e. no image has been processed.)')

    return parser.parse_args(argv)

if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))

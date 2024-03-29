import os
import cv2

import sys
import argparse
import datetime
from tqdm import tqdm

# Import utilites
from vebits_api import bbox_util, detector_util, im_util, others_util
from vebits_api.xml_util import create_xml_file
from det_img2img import load_tensors, get_filtered_boxes

FONT = cv2.FONT_HERSHEY_SIMPLEX
CONFIDENCE_THRESHOLD = 0.5

DESCRIPTION = """This script loads Object Detection API's model(s) (up to two),
makes predictions on video provided (frame by frame) and save annotated images
as well as their labels to *.xml files. Each model can specifically be used
to predict specific classes.
"""


def process_frame_batch(frames,
                        img_save_paths,
                        num_transform,
                        sequence,
                        tensors,
                        tensors_2,
                        confidence_threshold):

    # Perform augmentation
    frames_aug = sequence(images=frames * num_transform)
    frames.extend(frames_aug)
    frames = np.asarray(frames)
    # Update number of images generated
    name, ext = os.path.splitext(img_save_paths[-1])
    num_img_generated = int(name.split("_")[-1])
    name = '_'.join(name.split("_")[:-1])
    for i in range(len(frames_aug)):
        num_img_generated += 1
        # Use the number of frame processed to name the files
        img_save_path = "{}_{}.jpg".format(name, num_img_generated)
        img_save_paths.append(img_save_path)

    boxes, scores, classes = detector_util.detect_objects(frames, tensors)
    if tensors_2 is not None:
        boxes_2, scores_2, classes_2 = detector_util.detect_objects(frames, tensors_2)

    frame_height, frame_width = frames.shape[1:3]

    for i in range(boxes.shape[0]):
        bboxes = get_filtered_boxes(
                            boxes=boxes[i],
                            scores=scores[i],
                            classes=classes[i],
                            class_to_be_detected=tensors["class_to_be_detected"],
                            labelmap_dict_inverse=tensors["labelmap_dict_inverse"],
                            confidence_threshold=confidence_threshold,
                            img_size=(frame_height, frame_width),
                        )
        if tensors_2 is not None:
            bboxes_2 = get_filtered_boxes(
                                boxes=boxes_2[i],
                                scores=scores_2[i],
                                classes=classes_2[i],
                                class_to_be_detected=tensors_2["class_to_be_detected"],
                                labelmap_dict_inverse=tensors_2["labelmap_dict_inverse"],
                                confidence_threshold=confidence_threshold,
                                img_size=(frame_height, frame_width),
                            )

            bboxes = bboxes + bboxes_2

        xml_util.create_xml_file(
            img_save_paths[i],
            frame_width,
            frame_height,
            bboxes,
        )

        im_util.save_imgs(frames, img_save_paths)

    return num_img_generated

def main(args):
    # Load models' tensors
    tensors = load_tensors(
                    args.inference_graph_path,
                    args.labelmap_path,
                    args.num_classes,
                    args.class_to_be_detected)

    if args.inference_graph_path_2 is None:
        dual = False
        tensors_2 = None
    else:
        dual = True
        tensors_2 = load_tensors(
                        args.inference_graph_path_2,
                        args.labelmap_path_2,
                        args.num_classes_2,
                        args.class_to_be_detected_2)
    # Read arguments
    batch_size = args.batch_size
    beginning = True
    scale = args.scale
    # Prepare for image augmentation
    sequence = create_sequence()
    num_transform = args.num_transform
    # Prepare for image rotation
    rotate = args.rotate
    if rotate is not None:
        if rotate % 90 != 0:
            raise ValueError("Invalid value for \'rotate\'")
        else:
            rotate = rotate % 360

    num_frame_passed = 0
    num_frame_processed = 0
    num_img_generated = 0
    num_frame_interval = args.num_frame_interval
    frames = []
    img_save_paths = []

    for video_path, output_dir in zip(args.video_paths, args.output_dirs):
        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)
        # Open video file
        video = cv2.VideoCapture(video_path)
        _, video_name = os.path.split(video_path)
        name, _ = os.path.splitext(video_name)
        # Start reading and processing frame by frame
        with tqdm() as t:
            while True:
                ret, frame = video.read()
                if not ret:
                    break
                # Wait until reached the end of the interval.
                num_frame_passed += 1
                if num_frame_passed % num_frame_interval != 0:
                    continue
                # If reached, then update the variables.
                num_frame_processed += 1
                num_img_generated += 1
                img_save_name = "{}_{}.jpg".format(name, num_img_generated)
                img_save_paths.append(os.path.join(output_dir, img_save_name))
                t.set_postfix(generated=num_img_generated, img=img_save_name)
                # If this is the first loop, then generate necessary variables and objects.
                if beginning:
                    if rotate == 90 or rotate == 270:
                        frame_width, frame_height = frame.shape[:2]
                    else:
                        frame_height, frame_width = frame.shape[:2]

                    frame_width = int(frame_width * scale)
                    frame_height = int(frame_height * scale)
                    beginning = False
                # Rotate frame
                if rotate:
                    frame = imutils.rotate_bound(frame, rotate)
                # Resize frame
                frame = cv2.resize(frame, (frame_width, frame_height))
                frames.append(frame)
                # Wait until batch_size number of frames are grabbed.
                if num_frame_processed % batch_size != 0:
                    continue
                # Process frames by batch
                num_img_generated = process_frame_batch(
                                        frames=frames,
                                        img_save_paths=img_save_paths,
                                        num_transform=num_transform,
                                        sequence=sequence,
                                        tensors=tensors,
                                        tensors_2=tensors_2,
                                        confidence_threshold=CONFIDENCE_THRESHOLD)
                t.set_postfix(generated=num_img_generated, img=img_save_name)
                # Reset each time one batch is processed
                frames = []
                img_save_paths = []
            # At the end of the loop, there might bt some leftover
            if frames != []:
                num_img_generated = process_frame_batch(
                                        frames=frames,
                                        img_save_paths=img_save_paths,
                                        num_transform=num_transform,
                                        sequence=sequence,
                                        tensors=tensors,
                                        tensors_2=tensors_2,
                                        confidence_threshold=CONFIDENCE_THRESHOLD)
                t.set_postfix(generated=num_img_generated, img=img_save_name)

            print('\n>>> Results: {} images generated to '
                  '{}'.format(num_img_generated, output_dir))
            # Clean up
            video.release()
            frames = []
            img_save_paths = []
            num_img_generated = 0


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=DESCRIPTION)

    parser.add_argument('inference_graph_path', type=str,
        help='Path to the first inference graph.')
    parser.add_argument('labelmap_path', type=str,
        help='Path to the label map of the first model.')
    parser.add_argument('num_classes', type=int,
        default=2, help='Number of classes the first model can detect.')
    parser.add_argument('class_to_be_detected', type=str,
        help='The class(es) to be predicted. If multiple, \
        separate each class with comma (e.g \'phone,not_phone\'). \
        Specify \'all\' to use all classes.')

    parser.add_argument('-i', '--inference_graph_path_2', type=str, default=None,
        help='Path to the second inference graph.')
    parser.add_argument('-l', '--labelmap_path_2', type=str, default=None,
        help='Path to the label map of the second model.')
    parser.add_argument('-n', '--num_classes_2', type=int, default=None,
        help='Number of classes the second model can detect.')
    parser.add_argument('-c', '--class_to_be_detected_2', type=str, default=None,
        help='The class(es) to be predicted. If multiple, \
        separate each class with comma (e.g \'phone,not_phone\')')

    parser.add_argument('-v', '--video_paths', type=str, nargs='+', required=True,
        help='All the paths to the videos you want to process,\
        separate by space (i.e. \' \').')
    parser.add_argument('-o', '--output_dirs', type=str, nargs='+', required=True,
        help='Directories to which images and their labels will be saved.')

    parser.add_argument('--rotate', type=int, default=0,
        help='Degree to rotate the video.')
    parser.add_argument('--batch_size', type=int, default=4,
        help='Number of images to process each loop.')
    parser.add_argument('--num_transform', type=int, default=3,
        help='Number of times to perform augmentation.')
    parser.add_argument('--scale', type=float, default=0.5,
        help='Scale to resize the images.')
    parser.add_argument('--num_frame_interval', type=int, default=15,
        help='Length of frame interval to skip.')

    return parser.parse_args(argv)

if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))

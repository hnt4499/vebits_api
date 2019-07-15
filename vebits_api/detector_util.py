# Utilities for object detector.

import os
import sys
from threading import Thread
from datetime import datetime
from collections import defaultdict

import numpy as np
import tensorflow as tf
import cv2
# DarkNet/Darkflow for YOLO
from darkflow.net.build import TFNet
# Multiprocessing
from multiprocessing.pool import ThreadPool
pool = ThreadPool()

from . import labelmap_util
from . import im_util


# Load Tensorflow inference graph into memory
def load_inference_graph_tf(inference_graph_path):
    # load frozen tensorflow model into memory
    detection_graph = tf.Graph()
    with detection_graph.as_default():
        od_graph_def = tf.GraphDef()
        with tf.gfile.GFile(inference_graph_path, 'rb') as fid:
            serialized_graph = fid.read()
            od_graph_def.ParseFromString(serialized_graph)
            tf.import_graph_def(od_graph_def, name='')
        sess = tf.Session(graph=detection_graph)

    image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
    detection_boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
    detection_scores = detection_graph.get_tensor_by_name('detection_scores:0')
    detection_classes = detection_graph.get_tensor_by_name('detection_classes:0')
    num_detections = detection_graph.get_tensor_by_name('num_detections:0')

    tensors = {
        "sess": sess,
        "image_tensor": image_tensor,
        "detection_boxes": detection_boxes,
        "detection_scores": detection_scores,
        "detection_classes": detection_classes,
        "num_detections": num_detections
    }

    return tensors


def load_inference_graph_yolo(inference_graph_path, meta_path,
                              gpu_usage=0.95, confidence_threshold=0.5):
    """Load YOLO's inference graph into memory.

    Parameters
    ----------
    inference_graph_path : str
        Path to the inference graph generated by using
        --savepb option of Darkflow.
    meta_path : type
        Path to the metadata file generated by using
        --savepb option of Darkflow.
    gpu_usage: float
        By default, 95% of GPU power will be used.
    confidence_threshold: float

    Returns
    -------
    tensors
        List of tensors used for making inference.

    """
    # Pass a fake `FLAGS` object to Darkflow
    flags = {"pbLoad": inference_graph_path,
             "metaLoad": meta_path, "gpu": gpu_usage,
             "thresh": confidence_threshold}
    yolo_net = TFNet(flags)
    return {"yolo_net": yolo_net}

# Load a frozen infrerence graph into memory
def load_inference_graph(inference_graph_path, meta_path=None,
                         gpu_usage=0.95, confidence_threshold=0.5):
    """Interface to load either Tensorflow or Darknet's YOLO inference graph
    into memory.

    Parameters
    ----------
    inference_graph_path : str
    meta_path : str
        Path to the meta file generated by using option `--savepb` of Darkflow.
        If None, Tensorflow inference graph will be loaded.
        If not None, YOLO inference graph will be loaded.
    gpu_usage: float
        Used for YOLO graph when meta_path is specified. 95% of GPU memory
        will be used by default.
    confidence_threshold: float

    Returns
    -------
    tensors
        List of tensors used for making inference.

    """
    if meta_path is None:
        return load_inference_graph_tf(inference_graph_path)
    else:
        return load_inference_graph_yolo(inference_graph_path,
                                         meta_path, gpu_usage,
                                         confidence_threshold)


def load_tensors(inference_graph_path, labelmap_path,
                 num_classes=None, meta_path=None,
                 gpu_usage=0.95, confidence_threshold=0.5):
    """Interface to load either Tensorflow or Darknet's YOLO inference graph as
    well as other information such as label map into memory.

    Parameters
    ----------
    inference_graph_path : str
    labelmap_path : str
    num_classes : int
        Number of classes the model can detect. If not specified, it will
        be inferred from label map.
    meta_path : str
        Path to the meta file generated by using option `--savepb` of Darkflow.
        If None, Tensorflow inference graph will be loaded.
        If not None, YOLO inference graph will be loaded.
    confidence_threshold: float
        Confidence threshold.

    Returns
    -------
    tensors
        List of tensors used for making inference.

    """
    tensors = load_inference_graph(inference_graph_path, meta_path,
                                   gpu_usage, confidence_threshold)
    labelmap_dict = labelmap_util.get_label_map_dict(labelmap_path)
    labelmap_dict_inverse = labelmap_util.get_label_map_dict_inverse(labelmap_dict)
    # If `num_classes` is not specified, it will be inferred from labelmap.
    if num_classes is None:
        num_classes = len(labelmap_dict)
    category_index = labelmap_util.load_category_index(labelmap_path, num_classes)

    tensors["labelmap_dict"] = labelmap_dict
    tensors["labelmap_dict_inverse"] = labelmap_dict_inverse
    tensors["category_index"] = category_index

    return tensors


def detect_objects_tf(imgs, tensors):
    sess = tensors["sess"]
    image_tensor = tensors["image_tensor"]
    detection_boxes = tensors["detection_boxes"]
    detection_scores = tensors["detection_scores"]
    detection_classes = tensors["detection_classes"]
    num_detections = tensors["num_detections"]

    (boxes, scores, classes, num) = sess.run(
        [detection_boxes, detection_scores,
            detection_classes, num_detections],
        feed_dict={image_tensor: imgs})

    return boxes, scores, classes


def detect_objects_yolo(imgs, tensors):
    """This function makes use of multiprocessing to make predictions on batch.

    Parameters
    ----------
    imgs : list-like of images
    tensors : dict
        Contains tensors needed for making predictions.

    Returns
    -------
    boxes: tuple
        Tuple of length `n_images` containing list of boxes for each image.
    scores: tuple
    classes: tuple
        Note that this object already converts label index to label (e.g from 1
        to "phone").

    """

    yolo_net = tensors["yolo_net"]

    boxes_data = pool.map(lambda img: return_predict(yolo_net, img), imgs)
    boxes, scores, classes = list(zip(*boxes_data))
    return np.array(boxes), np.array(scores), np.array(classes)


def return_predict(net, img):
    """
    This function was modified from `darkflow.net.flow.return_predict`
    to work appropriately with this API.
    """
    h, w, _ = img.shape
    img = im_util.resize_padding(img, net.meta["inp_size"][:2])
    img = net.framework.resize_input(img)
    this_inp = np.expand_dims(img, 0)
    feed_dict = {net.inp : this_inp}

    out = net.sess.run(net.out, feed_dict)[0]
    boxes = net.framework.findboxes(out)
    threshold = net.FLAGS.threshold
    boxes_out, scores, classes = [], [], []
    for box in boxes:
        tmpBox = net.framework.process_box(box, h, w, threshold)
        if tmpBox is None:
            continue
        boxes_out.append([tmpBox[0], tmpBox[2], tmpBox[1], tmpBox[3]])
        scores.append(tmpBox[6])
        # This API uses class index starting from 1
        classes.append(tmpBox[5] + 1)
    return np.array(boxes_out), np.array(scores), np.array(classes)


def detect_objects(img, tensors):
    dims = img.ndim
    if dims == 3:
        img = np.expand_dims(img, axis=0)
    # Detect by yolo
    if "yolo_net" in tensors:
        boxes, scores, classes = detect_objects_yolo(img, tensors)
        if dims == 3:
            return boxes[0], scores[0], classes[0]
        else:
            return boxes, scores, classes

    # Detect by API
    else:
        boxes, scores, classes = detect_objects_tf(img, tensors)
        if dims == 3:
            return np.squeeze(boxes), np.squeeze(scores), np.squeeze(classes)
        else:
            return boxes, scores, classes


# Code to thread reading camera input.
# Source : Adrian Rosebrock
# https://www.pyimagesearch.com/2017/02/06/faster-video-file-fps-with-cv2-videocapture-and-opencv/
class WebcamVideoStream:
    def __init__(self, src, width, height):
        # initialize the video camera stream and read the first frame
        # from the stream
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        (self.grabbed, self.frame) = self.stream.read()

        # initialize the variable used to indicate if the thread should
        # be stopped
        self.stopped = False

    def start(self):
        # start the thread to read frames from the video stream
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        while True:
            # if the thread indicator variable is set, stop the thread
            if self.stopped:
                return

            # otherwise, read the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        # return the frame most recently read
        return self.frame

    def size(self):
        # return size of the capture device
        return self.stream.get(3), self.stream.get(4)

    def stop(self):
        # indicate that the thread should be stopped
        self.stopped = True

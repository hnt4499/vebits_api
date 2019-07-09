import cv2
from vebits_api.bbox_util import BBox, BBoxes
from vebits_api.others_util import convert, raise_type_error

FONT = cv2.FONT_HERSHEY_SIMPLEX
colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (100, 100, 100), (0, 255, 0)]


def _draw_box_on_image(img, box, label, color):
    # Use default color if `color` is not specified.
    if color is None:
        color = colors[0]
    p1 = (int(box[0]), int(box[1]))
    p2 = (int(box[2]), int(box[3]))
    cv2.rectangle(img, p1, p2, color, 3, 1)
    if label is not None:
        cv2.putText(img, label, p1, FONT, 0.75, color, 2, cv2.LINE_AA)
    return img


def draw_box_on_image(img, box, label=None, color=None):
    if isinstance(box, BBox):
        return _draw_box_on_image(img, box.to_xyxy_array(), label, color)
    else:
        try:
            box = convert(box,
                          lambda x: np.asarray(x, dtype=np.int32),
                          np.ndarray)
            if box.shape != (4,):
                raise ValueError("Input bounding box must be of shape (4,), "
                                 "got shape {} instead".format(box.shape))
            else:
                return _draw_box_on_image(img, box, label, color)
        except:
            raise_type_error(type(box), [BBox, np.ndarray])


def _draw_boxes_on_image(img, boxes, labels=None, labelmap_dict=None):
    for i in range(boxes.shape[0]):
        box = boxes[i]
        cl = classes[i]
        p1 = (int(box[0]), int(box[1]))
        p2 = (int(box[2]), int(box[3]))

        if classes is not None:
            cl_num = labelmap_dict[cl]
            cv2.putText(img, cl, p1, FONT, 0.75, colors[cl_num], 2, cv2.LINE_AA)
            cv2.rectangle(img, p1, p2, colors[cl_num], 3, 1)
        else:
            cv2.rectangle(img, p1, p2, colors[0], 3, 1)
    return img


def draw_number(img, number, loc=None):
    loc = (20, 50) if loc is None else loc
    cv2.putText(img, str(number), loc,
                FONT, 1.25, colors[0], 2)
    return img

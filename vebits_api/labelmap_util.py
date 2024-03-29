"""Label map utility functions."""

import logging
# Try importing tensorflow
try:
    import tensorflow as tf
    tf_imported = True
except ModuleNotFoundError:
    print("No tensorflow installation found")
    tf_imported = False
    
from google.protobuf import text_format

from . import string_int_label_map_pb2
from .others_util import check_import


def _validate_label_map(label_map):
    """Checks if a label map is valid.

    Args:
      label_map: StringIntLabelMap to validate.

    Raises:
      ValueError: if label map is invalid.
    """
    for item in label_map.item:
        if item.id < 1:
            raise ValueError('Label map ids should be >= 1.')


def create_category_index(categories):
    """Creates dictionary of COCO compatible categories keyed by category id.

    Args:
      categories: a list of dicts, each of which has the following keys:
        'id': (required) an integer id uniquely identifying this category.
        'name': (required) string representing category name
          e.g., 'cat', 'dog', 'pizza'.

    Returns:
      category_index: a dict containing the same entries as categories, but keyed
        by the 'id' field of each category.
    """
    category_index = {}
    for cat in categories:
        category_index[cat['id']] = cat
    return category_index


def convert_label_map_to_categories(label_map,
                                    max_num_classes,
                                    use_display_name=True):
    """Loads label map proto and returns categories list compatible with eval.

    This function loads a label map and returns a list of dicts, each of which
    has the following keys:
      'id': (required) an integer id uniquely identifying this category.
      'name': (required) string representing category name
        e.g., 'cat', 'dog', 'pizza'.
    We only allow class into the list if its id-label_id_offset is
    between 0 (inclusive) and max_num_classes (exclusive).
    If there are several items mapping to the same id in the label map,
    we will only keep the first one in the categories list.

    Args:
      label_map: a StringIntLabelMapProto or None.  If None, a default categories
        list is created with max_num_classes categories.
      max_num_classes: maximum number of (consecutive) label indices to include.
      use_display_name: (boolean) choose whether to load 'display_name' field
        as category name.  If False or if the display_name field does not exist,
        uses 'name' field as category names instead.
    Returns:
      categories: a list of dictionaries representing all possible categories.
    """
    categories = []
    list_of_ids_already_added = []
    if not label_map:
        label_id_offset = 1
        for class_id in range(max_num_classes):
            categories.append({
                'id': class_id + label_id_offset,
                'name': 'category_{}'.format(class_id + label_id_offset)
            })
        return categories
    for item in label_map.item:
        if not 0 < item.id <= max_num_classes:
            logging.info('Ignore item %d since it falls outside of requested '
                         'label range.', item.id)
            continue
        if use_display_name and item.HasField('display_name'):
            name = item.display_name
        else:
            name = item.name
        if item.id not in list_of_ids_already_added:
            list_of_ids_already_added.append(item.id)
            categories.append({'id': item.id, 'name': name})
    return categories


@check_import([tf_imported], ["tensorflow"])
def load_labelmap(path):
    """Loads label map proto.

    Args:
      path: path to StringIntLabelMap proto text file.
    Returns:
      a StringIntLabelMapProto
    """
    with tf.gfile.GFile(path, 'r') as fid:
        label_map_string = fid.read()
        label_map = string_int_label_map_pb2.StringIntLabelMap()
        try:
            text_format.Merge(label_map_string, label_map)
        except text_format.ParseError:
            label_map.ParseFromString(label_map_string)
    _validate_label_map(label_map)
    return label_map


def load_category_index(label_map_path, num_classes):
    """Load a labelmap and returns a category index.

    Args:
      label_map_path: path to label_map.
      num_classes: number of classes.

    Returns:
      A category_index object.
    """
    label_map = load_labelmap(label_map_path)
    categories = convert_label_map_to_categories(
        label_map, max_num_classes=num_classes, use_display_name=True)
    category_index = create_category_index(categories)

    return category_index


def get_label_map_dict(label_map_path):
    """Reads a label map and returns a dictionary of label names to id.

    Args:
      label_map_path: path to label_map.

    Returns:
      A dictionary mapping label names to id.
    """
    label_map = load_labelmap(label_map_path)
    label_map_dict = {}
    for item in label_map.item:
        label_map_dict[item.name] = item.id
    return label_map_dict


def get_label_map_dict_from_category_index(category_index):
    """Reads a category index and returns a dictionary of label names to id.

    Args:
      category_index: category_index object.

    Returns:
      A dictionary mapping label names to id.
    """

    labels = {}

    for i in range(len(category_index)):
        element = category_index[i + 1]
        labels[element["id"]] = element["name"]

    return labels


def get_label_map_dict_inverse(labelmap_dict):
    labelmap_dict_inverse = {}
    for cl, num in labelmap_dict.items():
        labelmap_dict_inverse[num] = cl
    return labelmap_dict_inverse

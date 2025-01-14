"""Run DeepLab-LargeFOV on a given image.

This script computes a segmentation mask for a given image.
"""



import argparse
from datetime import datetime
import os
import sys
import time

from PIL import Image

import tensorflow as tf
import numpy as np

from deeplab_lfov import DeepLabLFOVModel, ImageReader, decode_labels

SAVE_DIR = './output/'
IMG_MEAN = np.array((104.00698793,116.66876762,122.67891434), dtype=np.float32)

def get_arguments():
    """Parse all the arguments provided from the CLI.
    
    Returns:
      A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="DeepLabLFOV Network Inference.")
    parser.add_argument("img_path", type=str,
                        help="Path to the RGB image file.")
    parser.add_argument("model_weights", type=str,
                        help="Path to the file with model weights.")
    parser.add_argument("--save_dir", type=str, default=SAVE_DIR,
                        help="Where to save predicted mask.")
    return parser.parse_args()

def load(saver, sess, ckpt_path):
    '''Load trained weights.
    
    Args:
      saver: TensorFlow saver object.
      sess: TensorFlow session.
      ckpt_path: path to checkpoint file with parameters.
    ''' 
    saver.restore(sess, ckpt_path)
    print("Restored model parameters from {}".format(ckpt_path))

def main():
    """Create the model and start the evaluation process."""
    tf.compat.v1.disable_eager_execution()
    args = get_arguments()
    
    # Prepare image.
    img = tf.image.decode_jpeg(tf.io.read_file(args.img_path), channels=3)
    # Convert RGB to BGR.
    # jmg_r, img_g, img_b = tf.split(axis=2, num_or_size_splits=3, value=img)
    # img = tf.cast(tf.concat(2, [img_b, img_g, img_r]), dtype=tf.float32)
    red, green, blue = tf.unstack(img, axis=2)
    img = tf.cast(tf.stack([blue, green, red], axis=2), dtype=tf.float32)
    # Extract mean.
    img -= IMG_MEAN 
    
    # Create network.
    net = DeepLabLFOVModel()

    # Which variables to load.
    trainable = tf.compat.v1.trainable_variables()
    
    # Predictions.
    pred = net.preds(tf.expand_dims(img, axis=0))
      
    # Set up TF session and initialize variables. 
    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.compat.v1.Session(config=config)
    init = tf.compat.v1.initialize_all_variables()
    
    sess.run(init)
    
    # Load weights.
    saver = tf.compat.v1.train.Saver(var_list=trainable)
    load(saver, sess, args.model_weights)
    
    # Perform inference.
    preds = sess.run([pred])
    
    msk = decode_labels(np.array(preds)[0, 0, :, :, 0])
    im = Image.fromarray(msk)
    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)
    im.save(args.save_dir + 'mask.png')
    
    print('The output file has been saved to {}'.format(args.save_dir + 'mask.png'))

    
if __name__ == '__main__':
    main()

import os

import numpy as np
import tensorflow as tf

IMG_MEAN = np.array((104.00698793,116.66876762,122.67891434), dtype=np.float32)

def read_labeled_image_list(data_dir, data_list):
    """Reads txt file containing paths to images and ground truth masks.
    
    Args:
      data_dir: path to the directory with images and masks.
      data_list: path to the file with lines of the form '/path/to/image /path/to/mask'.
       
    Returns:
      Two lists with all file names for images and masks, respectively.
    """
    f = open(data_list, 'r')
    images = []
    masks = []
    for line in f:
        image, mask = line.strip("\n").split(' ')
        images.append(data_dir + image)
        masks.append(data_dir + mask)
    return images, masks

def read_images_from_disk(input_queue, input_size, random_scale): 
    """Read one image and its corresponding mask with optional pre-processing.
    
    Args:
      input_queue: tf queue with paths to the image and its mask.
      input_size: a tuple with (height, width) values.
                  If not given, return images of original size.
      random_scale: whether to randomly scale the images prior
                    to random crop.
      
    Returns:
      Two tensors: the decoded image and its mask.
    """
    img_contents = tf.io.read_file(input_queue[0])
    label_contents = tf.io.read_file(input_queue[1])
    
    img = tf.image.decode_jpeg(img_contents, channels=3)
    label = tf.image.decode_png(label_contents, channels=1)
    if input_size is not None:
        h, w = input_size
        if random_scale:
            scale = tf.random.uniform([1], minval=0.75, maxval=1.25, dtype=tf.float32, seed=None)
            h_new = tf.cast(tf.mul(tf.cast(tf.shape(input=img)[0], dtype=tf.float32), scale), dtype=tf.int32)
            w_new = tf.cast(tf.mul(tf.cast(tf.shape(input=img)[1], dtype=tf.float32), scale), dtype=tf.int32)
            new_shape = tf.squeeze(tf.pack([h_new, w_new]), axis=[1])
            img = tf.image.resize(img, new_shape)
            label = tf.image.resize(tf.expand_dims(label, 0), new_shape, method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
            label = tf.squeeze(label, axis=[0]) # resize_image_with_crop_or_pad accepts 3D-tensor.
        img = tf.image.resize_with_crop_or_pad(img, h, w)
        label = tf.image.resize_with_crop_or_pad(label, h, w)
    # RGB -> BGR.
    img_r, img_g, img_b = tf.split(split_dim=2, num_split=3, value=img)
    img = tf.cast(tf.concat(2, [img_b, img_g, img_r]), dtype=tf.float32)
    # Extract mean.
    img -= IMG_MEAN 
    return img, label

class ImageReader(object):
    '''Generic ImageReader which reads images and corresponding segmentation
       masks from the disk, and enqueues them into a TensorFlow queue.
    '''

    def __init__(self, data_dir, data_list, input_size, random_scale, coord):
        '''Initialise an ImageReader.
        
        Args:
          data_dir: path to the directory with images and masks.
          data_list: path to the file with lines of the form '/path/to/image /path/to/mask'.
          input_size: a tuple with (height, width) values, to which all the images will be resized.
          random_scale: whether to randomly scale the images prior to random crop.
          coord: TensorFlow queue coordinator.
        '''
        self.data_dir = data_dir
        self.data_list = data_list
        self.input_size = input_size
        self.coord = coord
        
        self.image_list, self.label_list = read_labeled_image_list(self.data_dir, self.data_list)
        self.images = tf.convert_to_tensor(value=self.image_list, dtype=tf.string)
        self.labels = tf.convert_to_tensor(value=self.label_list, dtype=tf.string)
        self.queue = tf.compat.v1.train.slice_input_producer([self.images, self.labels],
                                                   shuffle=input_size is not None) # Not shuffling if it is val.
        self.image, self.label = read_images_from_disk(self.queue, self.input_size, random_scale) 

    def dequeue(self, num_elements):
        '''Pack images and labels into a batch.
        
        Args:
          num_elements: the batch size.
          
        Returns:
          Two tensors of size (batch_size, h, w, {3,1}) for images and masks.'''
        image_batch, label_batch = tf.compat.v1.train.batch([self.image, self.label],
                                                  num_elements)
        return image_batch, label_batch

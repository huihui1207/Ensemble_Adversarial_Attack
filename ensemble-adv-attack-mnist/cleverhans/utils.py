from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import random
import numpy as np
from six.moves import xrange
import warnings
import matplotlib.pyplot as plt
import os
import scipy.misc

known_number_types = (int, float, np.float16, np.float32, np.float64,
                      np.int8, np.int16, np.int32, np.int32, np.int64,
                      np.uint8, np.uint16, np.uint32, np.uint64)


class _ArgsWrapper(object):
    """
    Wrapper that allows attribute access to dictionaries
    """

    def __init__(self, args):
        if not isinstance(args, dict):
            args = vars(args)
        self.args = args

    def __getattr__(self, name):
        return self.args.get(name)


class AccuracyReport(object):
    """
    An object summarizing the accuracy results for experiments involving
    training on clean examples or adversarial examples, then evaluating
    on clean or adversarial examples.
    """

    def __init__(self):
        self.clean_train_clean_eval = 0.
        self.clean_train_adv_eval = 0.
        self.adv_train_clean_eval = 0.
        self.adv_train_adv_eval = 0.

        # Training data accuracy results to be used by tutorials
        self.train_clean_train_clean_eval = 0.
        self.train_clean_train_adv_eval = 0.
        self.train_adv_train_clean_eval = 0.
        self.train_adv_train_adv_eval = 0.


def batch_indices(batch_nb, data_length, batch_size):
    """
    This helper function computes a batch start and end index
    :param batch_nb: the batch number
    :param data_length: the total length of the data being parsed by batches
    :param batch_size: the number of inputs in each batch
    :return: pair of (start, end) indices
    """
    # Batch start and end index
    start = int(batch_nb * batch_size)
    end = int((batch_nb + 1) * batch_size)

    # When there are not enough inputs left, we reuse some to complete the
    # batch
    if end > data_length:
        shift = end - data_length
        start -= shift
        end -= shift

    return start, end


def other_classes(nb_classes, class_ind):
    """
    Returns a list of class indices excluding the class indexed by class_ind
    :param nb_classes: number of classes in the task
    :param class_ind: the class index to be omitted
    :return: list of class indices excluding the class indexed by class_ind
    """
    if class_ind < 0 or class_ind >= nb_classes:
        error_str = "class_ind must be within the range (0, nb_classes - 1)"
        raise ValueError(error_str)

    other_classes_list = list(range(nb_classes))
    other_classes_list.remove(class_ind)

    return other_classes_list


def to_categorical(y, num_classes=None):
    """
    Converts a class vector (integers) to binary class matrix.
    This is adapted from the Keras function with the same name.
    :param y: class vector to be converted into a matrix
              (integers from 0 to num_classes).
    :param num_classes: num_classes: total number of classes.
    :return: A binary matrix representation of the input.
    """
    y = np.array(y, dtype='int').ravel()
    if not num_classes:
        num_classes = np.max(y) + 1
    n = y.shape[0]
    categorical = np.zeros((n, num_classes))
    categorical[np.arange(n), y] = 1
    return categorical


def random_targets(gt, nb_classes):
    """
    Take in an array of correct labels and randomly select a different label
    for each label in the array. This is typically used to randomly select a
    target class in targeted adversarial examples attacks (i.e., when the
    search algorithm takes in both a source class and target class to compute
    the adversarial example).
    :param gt: the ground truth (correct) labels. They can be provided as a
               1D vector or 2D array of one-hot encoded labels.
    :param nb_classes: The number of classes for this task. The random class
                       will be chosen between 0 and nb_classes such that it
                       is different from the correct class.
    :return: A numpy array holding the randomly-selected target classes
             encoded as one-hot labels.
    """
    # If the ground truth labels are encoded as one-hot, convert to labels.
    if len(gt.shape) == 2:
        gt = np.argmax(gt, axis=1)

    # This vector will hold the randomly selected labels.
    result = np.zeros(gt.shape, dtype=np.int32)

    for class_ind in xrange(nb_classes):
        # Compute all indices in that class.
        in_cl = gt == class_ind
        size = np.sum(in_cl)

        # Compute the set of potential targets for this class.
        potential_targets = other_classes(nb_classes, class_ind)

        # Draw with replacement random targets among the potential targets.
        result[in_cl] = np.random.choice(potential_targets, size=size)

    # Encode vector of random labels as one-hot labels.
    result = to_categorical(result, nb_classes)
    result = result.astype(np.int32)

    return result


def pair_visual(original, adversarial, figure=None):
    """
    This function displays two images: the original and the adversarial sample
    :param original: the original input
    :param adversarial: the input after perterbations have been applied
    :param figure: if we've already displayed images, use the same plot
    :return: the matplot figure to reuse for future samples
    """
    import matplotlib.pyplot as plt

    # Ensure our inputs are of proper shape
    assert (len(original.shape) == 2 or len(original.shape) == 3)

    # To avoid creating figures per input sample, reuse the sample plot
    if figure is None:
        plt.ion()
        figure = plt.figure()
        figure.canvas.set_window_title('Cleverhans: Pair Visualization')

    # Add the images to the plot
    perterbations = adversarial - original
    for index, image in enumerate((original, perterbations, adversarial)):
        figure.add_subplot(1, 3, index + 1)
        plt.axis('off')

        # If the image is 2D, then we have 1 color channel
        if len(image.shape) == 2:
            plt.imshow(image, cmap='gray')
        else:
            plt.imshow(image)

        # Give the plot some time to update
        plt.pause(0.01)

    # Draw the plot and return
    plt.show()
    return figure


def grid_visual(data):
    """
    This function displays a grid of images to show full misclassification
    :param data: grid data of the form;
        [nb_classes : nb_classes : img_rows : img_cols : nb_channels]
    :return: if necessary, the matplot figure to reuse
    """
    import matplotlib.pyplot as plt

    # Ensure interactive mode is disabled and initialize our graph
    plt.ioff()
    figure = plt.figure()
    figure.canvas.set_window_title('Cleverhans: Grid Visualization')

    # Add the images to the plot
    num_cols = data.shape[0]
    num_rows = data.shape[1]
    num_channels = data.shape[4]
    current_row = 0
    for y in xrange(num_rows):
        for x in xrange(num_cols):
            figure.add_subplot(num_cols, num_rows, (x + 1) + (y * num_rows))
            plt.axis('off')

            if num_channels == 1:
                plt.imshow(data[x, y, :, :, 0], cmap='gray')
            else:
                plt.imshow(data[x, y, :, :, :])

    # Draw the plot and return
    plt.show()
    return figure


def display_leg_adv_sample(X_test, X_adv):
    """
        Display the testing sample and adversarial sample visually.
        :param sess: the TF session.
        :param X_test: the testing data for the oracle.
        :param Y_adv: the adversarial data for the oracle.
        :param preds: model output predictions label.
        :return:
    """
    # X_test_redu = (0.5 + tf.reshape(X_test, ((X_test.shape[0], 32, 32, 3)))) * 255
    # X_train, y_train, X_test1, y_test = ld.load_data(train_data_dir, test_data_dir)
    # X_test_redu = reduction_batch(X_test)
    # X_adv_redu = reduction_batch(X_adv)

    # Pick 6 random images

    sample_indexes = random.sample(range(len(X_test)), 10)

    legitimate_sample = [X_test[i] for i in sample_indexes]
    adversarial_sample = [X_adv[i] for i in sample_indexes]
    f, axarr = plt.subplots(3, 10)
    for j in range(10):
        axarr[0, j].imshow(np.reshape(legitimate_sample[j], (28, 28)), cmap='gray')
        axarr[1, j].imshow(np.reshape(adversarial_sample[j], (28, 28)), cmap='gray')
        axarr[2, j].imshow(np.reshape(adversarial_sample[j] - legitimate_sample[j], (28, 28)), cmap='gray')
        # plt.setp(axarr[0, j].get_xticklabels(), visible=False)
        # plt.setp(axarr[1, j].get_yticklabels(), visible=False)
        plt.pause(0.01)
    plt.show()


def display_leg_sample(X_test):
    f, a = plt.subplots(3, 5, figsize=(3, 10))

    for i in range(len(X_test)):
        a[0][i].imshow(np.reshape(X_test[i:i + 1], (28, 28)), cmap='gray')

    plt.show()


def save_leg_adv_sample(save_dir, X_test, X_adv):
    if os.path.exists(save_dir) is False:
        os.makedirs(save_dir)

    sample_indexes = random.sample(range(len(X_test)), 10)

    legitimate_sample = [X_test[i] for i in sample_indexes]
    adversarial_sample = [X_adv[i] for i in sample_indexes]
    for j in range(10):
        image_array = legitimate_sample[j]
        image_array = image_array.reshape(28, 28)
        filename = save_dir + 'mnist_test_%d.jpg' % j
        scipy.misc.toimage(image_array, cmin=0.0, cmax=1.0).save(filename)

    for j in range(10):
        image_array = adversarial_sample[j]
        image_array = image_array.reshape(28, 28)
        filename = save_dir + 'mnist_adv_%d.jpg' % j
        scipy.misc.toimage(image_array, cmin=0.0, cmax=1.0).save(filename)

    print('Please check: %s ' % save_dir)


def save_leg_adv_specified_by_user(save_dir, X_test, X_adv, y_test):
    if os.path.exists(save_dir) is False:
        os.makedirs(save_dir)

    for i in range(len(X_test[:200])):
        if np.argmax(y_test[i]) == 4 and i == 109:
            image_array_leg = X_test[i]
            image_array_leg = image_array_leg.reshape(28, 28)
            filename = save_dir + 'mnist_test_%d_label_4.jpg' % i
            scipy.misc.toimage(image_array_leg, cmin=0.0, cmax=1.0).save(filename)

            image_array_adv = X_adv[i]
            image_array_adv = image_array_adv.reshape(28, 28)
            filename = save_dir + 'mnist_adv_%d_label_4.jpg' % i
            scipy.misc.toimage(image_array_adv, cmin=0.0, cmax=1.0).save(filename)

    print('please check: %s ' % save_dir)


def conv_2d(*args, **kwargs):
    from cleverhans.utils_keras import conv_2d
    warnings.warn("utils.conv_2d is deprecated and may be removed on or after"
                  " 2018-01-05. Switch to utils_keras.conv_2d.")
    return conv_2d(*args, **kwargs)


def cnn_model(*args, **kwargs):
    from cleverhans.utils_keras import cnn_model
    warnings.warn("utils.cnn_model is deprecated and may be removed on or"
                  " after 2018-01-05. Switch to utils_keras.cnn_model.")
    return cnn_model(*args, **kwargs)

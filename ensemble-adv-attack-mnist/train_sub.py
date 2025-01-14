import os
import keras
import numpy as np
from keras import backend as K
from keras.utils.np_utils import to_categorical
from tensorflow.python.platform import flags
from keras.models import save_model
from cleverhans.utils_tf import model_train, model_eval
from cleverhans.utils_mnist import data_mnist
from cleverhans.utils_keras import cnn_model
from cleverhans.attacks_tf import jacobian_graph, jacobian_augmentation
from tf_utils import tf_train, tf_test_error_rate, batch_eval
from mnist import model_mnist, set_mnist_flags, data_gen_mnist, load_model, substitute_model


FLAGS = flags.FLAGS

def train_sub(sess, x, y, bbox_preds, X_sub, Y_sub, nb_classes,
              nb_epochs_s, batch_size, learning_rate, data_aug, lmbda, model_type):
    """
    This function creates the substitute by alternatively
    augmenting the training data and training the substitute.
    :param sess: TF session
    :param x: input TF placeholder
    :param y: output TF placeholder
    :param bbox_preds: output of black-box model predictions
    :param X_sub: initial substitute training data
    :param Y_sub: initial substitute training labels
    :param nb_classes: number of output classes
    :param nb_epochs_s: number of epochs to train substitute model
    :param batch_size: size of training batches
    :param learning_rate: learning rate for training
    :param data_aug: number of times substitute training data is augmented
    :param lmbda: lambda from arxiv.org/abs/1602.02697
    :return:
    """
    # Define TF model graph (for the black-box model)
    # model_sub = model_mnist(type=model_type)
    model_sub = substitute_model()
    preds_sub = model_sub(x)
    print("Defined TensorFlow model graph for the substitute.")

    # Define the Jacobian symbolically using TensorFlow
    grads = jacobian_graph(preds_sub, x, nb_classes)

    # Train the substitute and augment dataset alternatively
    for rho in xrange(data_aug):
        print("Substitute training epoch #" + str(rho))
        train_params = {
            'nb_epochs': nb_epochs_s,
            'batch_size': batch_size,
            'learning_rate': learning_rate
        }
        model_train(sess, x, y, preds_sub, X_sub, to_categorical(Y_sub),
                    init_all=False, verbose=False, args=train_params)

        # If we are not at last substitute training iteration, augment dataset
        if rho < data_aug - 1:
            print("Augmenting substitute training data.")
            # Perform the Jacobian augmentation
            X_sub = jacobian_augmentation(sess, x, X_sub, Y_sub, grads, lmbda)

            print("Labeling substitute training data.")
            # Label the newly generated synthetic points using the black-box
            Y_sub = np.hstack([Y_sub, Y_sub])
            X_sub_prev = X_sub[int(len(X_sub)/2):]
            bbox_val = batch_eval([x], [bbox_preds], [X_sub_prev])[0]
            # Note here that we take the argmax because the adversary
            # only has access to the label (not the probabilities) output
            # by the black-box model
            Y_sub[int(len(X_sub)/2):] = np.argmax(bbox_val, axis=1)

    return model_sub, preds_sub

def main(model_name, model_type):
    np.random.seed(0)
    assert keras.backend.backend() == "tensorflow"
    set_mnist_flags()
    
    flags.DEFINE_bool('NUM_EPOCHS', args.epochs, 'Number of epochs')

    # Get MNIST test data
    X_train, Y_train, X_test, Y_test = data_mnist()

    # Initialize substitute training set reserved for adversary
    X_sub = X_test[:300]
    Y_sub = np.argmax(Y_test[:300], axis=1)

    # Redefine test set as remaining samples unavailable to adversaries
    X_test = X_test[300:]
    Y_test = Y_test[300:]

    x = K.placeholder((None,
                       FLAGS.IMAGE_ROWS,
                       FLAGS.IMAGE_COLS,
                       FLAGS.NUM_CHANNELS
                       ))

    y = K.placeholder(shape=(None, FLAGS.NUM_CLASSES))

    # Load Black-Box model
    model = load_model(blackbox_name)
    prediction = model(x)

    train_sub_out = train_sub(K.get_session(), x, y, prediction, X_sub, Y_sub, nb_classes=FLAGS.NUM_CLASSES,
                                     nb_epochs_s=args.epochs, batch_size=FLAGS.BATCH_SIZE, learning_rate=0.001, data_aug=6, lmbda=0.1, model_type=model_type)
    model_sub, preds_sub = train_sub_out
    eval_params = {
        'batch_size': FLAGS.BATCH_SIZE
    }

    # Finally print the result!
    # test_error = tf_test_error_rate(model_sub, x, X_test, Y_test)
    accuracy = model_eval(K.get_session(), x, y, preds_sub, X_test, Y_test, args=eval_params)
    print('Test accuracy of substitute on legitimate samples: %.3f%%' % accuracy)

    save_model(model_sub, model_name)
    json_string = model_sub.to_json()
    with open(model_name+'.json', 'wr') as f:
        f.write(json_string)

if __name__ == '__main__':
    SAVE_PATH = "models"
    blackbox_name = os.path.join(SAVE_PATH, "modelA")
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="path to model")
    parser.add_argument("--type", type=int, help="model type", default=1)
    parser.add_argument("--epochs", type=int, default=10, help="number of epochs")
    args = parser.parse_args()

    main(args.model, args.type)

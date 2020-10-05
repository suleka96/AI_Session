import tensorflow as tf
import matplotlib as mplt
mplt.use('agg')  # Must be before importing matplotlib.pyplot or pylab!
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from math import sqrt
import random as rn
import os
np.random.seed(1)


# Class to configure the Recurrent Neural Network
class RNNConfig():
    input_size = 1
    num_steps = 2
    hidden_size = 128
    num_layers = 1
    keep_prob = 0.8
    batch_size = 64
    init_learning_rate = 0.001
    learning_rate_decay = 0.99
    init_epoch = 3  # 5
    max_epoch = 30  # 100 or 50
    test_ratio = 0.2
    fileName = 'AIG.csv'
    graph = tf.Graph()
    min = 10
    max = 2000
    column = 'Close'

config = RNNConfig()


# Function to segment the dataset
def segmentation(data):

    seq = [price for tup in data[[config.column]].values for price in tup]

    seq = np.array(seq)

    # split into number of input_size
    seq = [np.array(seq[i * config.input_size: (i + 1) * config.input_size])
           for i in range(len(seq) // config.input_size)]

    # split into groups of num_steps
    X = np.array([seq[i: i + config.num_steps] for i in range(len(seq) - config.num_steps)])

    y = np.array([seq[i + config.num_steps] for i in range(len(seq) - config.num_steps)])

    return X, y


# Function to scale the dataset
def scale(data):

    data[config.column] = (data[config.column] - config.min) / (config.max - config.min)

    return data


# Function to preprocess the dataset
def pre_process():
    # plot_main_distribution()

    stock_data = pd.read_csv(config.fileName)
    stock_data = stock_data.reindex(index=stock_data.index[::-1])

    #---for segmenting original data ---------------------------------
    original_data = pd.read_csv(config.fileName)
    original_data = original_data.reindex(index=original_data.index[::-1])

    train_size = int(len(stock_data) * (1.0 - config.test_ratio))

    train_data = stock_data[:train_size]
    test_data = stock_data[train_size:]
    original_data = original_data[train_size:]

    #-------------- processing train data---------------------------------------

    scaled_train_data = scale(train_data)
    train_X , train_y = segmentation(scaled_train_data)

    # -------------- processing test data---------------------------------------

    scaled_test_data = scale(test_data)
    test_X, test_y = segmentation(scaled_test_data)

    #----segmenting original test data-----------------------------------------------

    nonescaled_X, nonescaled_y = segmentation(original_data)

    return train_X, train_y, test_X, test_y, nonescaled_y


# Function to generate the batches
def generate_batches(train_X, train_y, batch_size):
    num_batches = int(len(train_X)) // batch_size
    if batch_size * num_batches < len(train_X):
        num_batches += 1

    batch_indices = range(num_batches)
    # random.shuffle(batch_indices)
    for j in batch_indices:
        batch_X = train_X[j * batch_size: (j + 1) * batch_size]
        batch_y = train_y[j * batch_size: (j + 1) * batch_size]
        assert set(map(len, batch_X)) == {config.num_steps}
        yield batch_X, batch_y


def mean_absolute_percentage_error(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

def plot(true_vals,pred_vals,name):

    days = range(len(true_vals))
    plt.plot(days, true_vals, label='truth close')
    plt.plot(days, pred_vals, label='pred close')
    plt.legend(loc='upper left', frameon=False)
    plt.xlabel("day")
    plt.ylabel("closing price")
    plt.grid(ls='--')
    plt.savefig(name, format='png', bbox_inches='tight', transparent=False)
    plt.close()

def plot_main_distribution():
    original_data = pd.read_csv(config.fileName)
    original_data = original_data.reindex(index=original_data.index[::-1])
    days = range(len(original_data))
    plt.plot(days, original_data.Close, label='close values')
    plt.legend(loc='upper left', frameon=False)
    plt.xlabel("day")
    plt.ylabel("closing price")
    plt.grid(ls='--')
    plt.savefig("Original Close distribution.png", format='png', bbox_inches='tight', transparent=False)
    plt.close()


def train_test():

    train_X, train_y, test_X, test_y, nonescaled_y = pre_process()

    # Add nodes to the graph
    with config.graph.as_default():

        tf.set_random_seed(1)

        learning_rate = tf.placeholder(tf.float32, None, name="learning_rate")
        inputs = tf.placeholder(tf.float32, [None, config.num_steps, config.input_size], name="inputs")
        targets = tf.placeholder(tf.float32, [None,config.input_size], name="targets")
        keep_prob = tf.placeholder(tf.float32, None, name="keep_prob")


        # lstm_cell = tf.contrib.rnn.LSTMCell(config.hidden_size, state_is_tuple=True)

        lstm_cell = tf.contrib.rnn.BasicRNNCell(config.hidden_size)


        # Add dropout to the cell
        drop = tf.contrib.rnn.DropoutWrapper(lstm_cell, output_keep_prob=keep_prob)

        # Stack up multiple RNN layers, for deep learning
        cell = tf.contrib.rnn.MultiRNNCell([drop] * config.num_layers)

        val1, _ = tf.nn.dynamic_rnn(cell, inputs, dtype=tf.float32)

        val = tf.transpose(val1, [1, 0, 2])

        last = tf.gather(val, int(val.get_shape()[0]) - 1, name="last_lstm_output")

        weight = tf.Variable(tf.truncated_normal([config.hidden_size, config.input_size]))
        bias = tf.Variable(tf.constant(0.1, shape=[config.input_size]))

        prediction = tf.matmul(last, weight) + bias

        loss = tf.reduce_mean(tf.square(prediction - targets))
        optimizer = tf.train.AdamOptimizer(learning_rate)
        minimize = optimizer.minimize(loss)

    # --------------------training------------------------------------------------------

    with tf.Session(graph=config.graph) as sess:
        tf.set_random_seed(1)

        tf.global_variables_initializer().run()

        iteration = 1

        learning_rates_to_use = [
            config.init_learning_rate * (
                    config.learning_rate_decay ** max(float(i + 1 - config.init_epoch), 0.0)
            ) for i in range(config.max_epoch)]

        for epoch_step in range(config.max_epoch):

            current_lr = learning_rates_to_use[epoch_step]

            for batch_X, batch_y in generate_batches(train_X, train_y, config.batch_size):
                train_data_feed = {
                    inputs: batch_X,
                    targets: batch_y,
                    learning_rate: current_lr,
                    keep_prob: config.keep_prob
                }

                train_loss, _, value = sess.run([loss, minimize, val1], train_data_feed)

                if iteration % 5 == 0:
                    print("Epoch: {}/{}".format(epoch_step, config.max_epoch),
                          "Iteration: {}".format(iteration),
                          "Train loss: {:.3f}".format(train_loss))
                iteration += 1
        saver = tf.train.Saver()
        saver.save(sess, "checkpoints_stock/stock_pred.ckpt")

    # --------------------testing------------------------------------------------------

    with tf.Session(graph=config.graph) as sess:
        tf.set_random_seed(1)

        saver.restore(sess, tf.train.latest_checkpoint('checkpoints_stock'))

        test_data_feed = {
            learning_rate: 0.0,
            keep_prob: 1.0,
            inputs: test_X,
            targets: test_y,
        }

        test_pred = sess.run(prediction, test_data_feed)

        pred_vals = [(pred * (config.max - config.min)) + config.min for pred in test_pred]

        pred_vals = np.array(pred_vals)

        pred_vals = pred_vals.flatten()

        nonescaled_y = nonescaled_y.flatten()

        plot(nonescaled_y,pred_vals,"Stock price Prediction VS Truth uv2.png")

        meanSquaredError = mean_squared_error(nonescaled_y, pred_vals)
        rootMeanSquaredError = sqrt(meanSquaredError)
        print("RMSE:", rootMeanSquaredError)
        mae =mean_absolute_error(nonescaled_y, pred_vals)
        print("MAE:", mae)
        mape = mean_absolute_percentage_error(nonescaled_y, pred_vals)
        print("MAPE:", mape)


if __name__ == '__main__':
    train_test()

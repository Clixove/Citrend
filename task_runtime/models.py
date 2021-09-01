import json
import pickle
import typing
from io import BytesIO
import numpy as np
import pandas as pd
from django.core.files.base import ContentFile
from django.db import models
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error
import tensorflow as tf
from tensorflow.keras.layers import *

from task_manager.models import *


def list_union(a: typing.Iterable, b: typing.Iterable) -> list:
    a_set = set(a)
    c_set = a_set.intersection(b)
    return list(c_set)


def pre_processing_xy(factory: Factory):
    with open(factory.parsed_training_set.path, 'rb') as f:
        intermediate_data_handle = pickle.load(f)
    x = intermediate_data_handle['transaction']
    y = intermediate_data_handle['score']
    columns = Column.objects.filter(factory=factory)
    config = json.loads(factory.config)

    log_features = [z.name for z in columns.filter(log=True)]
    feat_name = [z.name for z in columns.filter(use=True)]
    x[log_features] = x[log_features].apply(lambda z: np.log(z + 1))
    mm_x = MinMaxScaler()
    x[feat_name] = mm_x.fit_transform(x[feat_name])
    mm_y = MinMaxScaler()
    y[[columns.get(is_score=True).name]] = mm_y.fit_transform(y[[columns.get(is_score=True).name]])
    intermediate_data_handle = ContentFile(pickle.dumps([mm_x, mm_y]))
    factory.normalizers.delete()
    factory.normalizers.save(f'factory_{factory.id}_normalizer.pkl', intermediate_data_handle)

    x_code = columns.get(belong_transaction=True, is_company=True).name
    y_code = columns.get(belong_transaction=False, is_company=True).name
    code_list = list_union(np.unique(x[x_code].values), np.unique(y[y_code].values))
    n_code = len(code_list)
    code_dict = dict(zip(code_list, range(n_code)))

    start_date = pd.Timestamp(config['from_datetime'])
    end_date = pd.Timestamp(config['to_datetime'])
    scale_date = np.linspace(start_date.value, end_date.value, config['periods'] + 1)
    scale_date = pd.to_datetime(scale_date)
    date_variable_name = columns.get(belong_transaction=True, is_date=True).name
    date_slicer = pd.cut(x[date_variable_name].values, scale_date, ordered=True)
    x[date_variable_name] = date_slicer.codes.astype('int32')

    feat_avg = np.nanmean(x[feat_name], axis=0)
    attributes = np.empty(shape=(n_code, config['periods'] + 1, len(feat_name)), dtype=np.float32)
    for (code, week), transaction in x.groupby([x_code, date_variable_name]):
        if code not in code_list:
            continue
        for i in range(len(feat_name)):
            name = feat_name[i]
            if columns.get(name=name).log:
                attributes[code_dict[code], week + 1, i] = np.log(np.nansum(np.exp(transaction[name]) - 1) + 1)
            else:
                attributes[code_dict[code], week + 1, i] = np.nanmean(transaction[name])
    for i in range(len(feat_name)):
        name = feat_name[i]
        if columns.get(name=name).fill_na_avg:
            attributes[:, :, i] = np.nan_to_num(attributes[:, :, i], nan=feat_avg[i], posinf=feat_avg[i],
                                                neginf=feat_avg[i])
        else:
            attributes[:, :, i] = np.nan_to_num(attributes[:, :, i], nan=0, posinf=0, neginf=0)

    score = np.full(n_code, 0, dtype=np.float32)
    for code, score_array in y.groupby(y_code):
        if code not in code_list:
            continue
        score[code_dict[code]] = np.nanmean(score_array[columns.get(is_score=True).name])

    idx_train, idx_valid, x_train, x_valid, y_train, y_valid = \
        train_test_split(code_list, attributes, score, train_size=0.8)

    dataset_compiled = ContentFile(pickle.dumps([idx_train, idx_valid, x_train, x_valid, y_train, y_valid]))
    factory.matrix.delete()
    factory.matrix.save(f'factory_{factory.id}_matrix.pkl', dataset_compiled)


def nn_train(factory: Factory):
    with open(factory.matrix.path, 'rb') as f:
        dataset = pickle.load(f)
    with open(factory.normalizers.path, 'rb') as f:
        _, mm_y = pickle.load(f)
    columns = Column.objects.filter(factory=factory)
    feat_name = [z.name for z in columns.filter(use=True)]
    config = json.loads(factory.config)

    input_ = Input(shape=(config['periods'] + 1, len(feat_name)))
    _, x, _ = LSTM(config['lstm_units'], return_state=True)(input_)
    for neuron_num in config['dense_units']:
        x = Dense(neuron_num, activation='relu')(x)
    my_model = tf.keras.models.Model(input_, x)
    my_model.compile(optimizer='adam', loss='mae')
    stop_early = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=config['patient'])

    empty_model = ContentFile(pickle.dumps(b'placeholder'))
    factory.model_0.delete()
    factory.model_0.save(f'factory_{factory.id}_model.h5', empty_model)

    idx_train, idx_valid, x_train, x_valid, y_train, y_valid = dataset
    save_best = tf.keras.callbacks.ModelCheckpoint(factory.model_0.path, monitor='val_loss', save_best_only=True)
    train_log = my_model.fit(
        x_train, y_train, validation_data=(x_valid, y_valid), epochs=config['steps'], batch_size=5000,
        callbacks=[stop_early, save_best], verbose=0
    )

    y_valid_hat = my_model.predict(x_valid)
    y_valid_hat_raw = mm_y.inverse_transform(y_valid_hat)
    y_valid_raw = mm_y.inverse_transform(y_valid[:, np.newaxis])
    factory.mae = mean_absolute_error(y_valid_raw, y_valid_hat_raw)
    factory.save()
    return train_log.history


class Predict(models.Model):
    factory = models.ForeignKey(Factory, models.CASCADE)
    predicted_time = models.DateTimeField(default=now)
    predicting_set = models.FileField(upload_to='data')

    parsed_predicting_set = models.FileField(upload_to='intermediate', blank=True, null=True)
    prediction = models.FileField(upload_to='results', blank=True, null=True)
    error_message = models.TextField(blank=True)


def pre_processing_x(x: pd.DataFrame, end_date: str, prediction: Predict):
    columns = Column.objects.filter(factory=prediction.factory)
    config = json.loads(prediction.factory.config)
    log_features = [z.name for z in columns.filter(log=True)]
    feat_name = [z.name for z in columns.filter(use=True)]
    x[log_features] = x[log_features].apply(lambda z: np.log(z + 1))
    with open(prediction.factory.normalizers.path, 'rb') as f:
        mm_x, _ = pickle.load(f)
    x[feat_name] = mm_x.transform(x[feat_name])

    x_code = columns.get(belong_transaction=True, is_company=True).name
    code_list = np.unique(x[x_code].values)
    n_code = len(code_list)
    code_dict = dict(zip(code_list, range(n_code)))

    end_date = pd.Timestamp(end_date)
    start_date = end_date - (pd.Timestamp(config['to_datetime']) - pd.Timestamp(config['from_datetime']))
    scale_date = np.linspace(start_date.value, end_date.value, config['periods'] + 1)
    scale_date = pd.to_datetime(scale_date)
    date_variable_name = columns.get(belong_transaction=True, is_date=True).name
    date_slicer = pd.cut(x[date_variable_name].values, scale_date, ordered=True)
    x[date_variable_name] = date_slicer.codes.astype('int32')

    feat_avg = np.nanmean(x[feat_name], axis=0)
    attributes = np.empty(shape=(n_code, config['periods'] + 1, len(feat_name)), dtype=np.float32)
    for (code, week), transaction in x.groupby([x_code, date_variable_name]):
        for i in range(len(feat_name)):
            name = feat_name[i]
            if columns.get(name=name).log:
                attributes[code_dict[code], week + 1, i] = np.log(np.nansum(np.exp(transaction[name]) - 1) + 1)
            else:
                attributes[code_dict[code], week + 1, i] = np.nanmean(transaction[name])
    for i in range(len(feat_name)):
        name = feat_name[i]
        if columns.get(name=name).fill_na_avg:
            attributes[:, :, i] = np.nan_to_num(attributes[:, :, i], nan=feat_avg[i], posinf=feat_avg[i],
                                                neginf=feat_avg[i])
        else:
            attributes[:, :, i] = np.nan_to_num(attributes[:, :, i], nan=0, posinf=0, neginf=0)
    intermediate_data_handle = ContentFile(pickle.dumps([code_list, attributes]))
    prediction.parsed_predicting_set.save(f'prediction_{prediction.id}_matrix.pkl', intermediate_data_handle)


def nn_predict(prediction: Predict):
    with open(prediction.parsed_predicting_set.path, 'rb') as f:
        index, x = pickle.load(f)
    with open(prediction.factory.normalizers.path, 'rb') as f:
        _, mm_y = pickle.load(f)
    my_model = tf.keras.models.load_model(prediction.factory.model_0.path)
    y_hat = my_model.predict(x, verbose=0)
    y_hat_raw = mm_y.inverse_transform(y_hat)
    report = pd.DataFrame({'companies': index, 'score': y_hat_raw.squeeze()})
    table_bin = BytesIO()
    with pd.ExcelWriter(table_bin) as f:
        report.to_excel(f, index=False)
    prediction.prediction.save(f'prediction_{prediction.id}.xlsx', table_bin)

"""
dataloader.py
"""

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def load_txt_dataset(file_path, test_size=0.2, random_state=42, with_scaling=True):

    data = np.loadtxt(file_path, delimiter=",")
    X, y = data[:, :-1], data[:, -1]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y)

    if with_scaling:
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_val = scaler.transform(X_val)

    X_train = np.c_[np.ones(X_train.shape[0]), X_train]
    X_val = np.c_[np.ones(X_val.shape[0]), X_val]

    return X_train, X_val, y_train, y_val, scaler

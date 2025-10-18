"""
Logistic Regression
"""

import numpy as np
import matplotlib.pyplot as plt
from dataloader import load_txt_dataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


"""data"""
def make_linear_data(n_per_class=100, naive=False, seed=39):
    np.random.seed(seed)
    mean1, mean2 = [1,1.5], [-1,-1.5]
    if naive == True:
        cov = np.array([[0.3 , 0.], [0., 0.5]])
    else:
        cov = np.array([[0.7 , 0.4], [0.4, 0.5]])
    X1 = np.random.multivariate_normal(mean1, cov, n_per_class)
    X2 = np.random.multivariate_normal(mean2, cov, n_per_class)
    X = np.vstack([X1,X2])
    y = np.hstack([np.ones(n_per_class), np.zeros(n_per_class)])
    return X, y

class LogisticRegression:
    def __init__(self, lr=0.1, lambda_=0.0, optimizer='gd',max_iter=200, tol=1e-6,
                 beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8):
        self.lr = lr
        self.lambda_ = lambda_
        self.optimizer = optimizer
        self.max_iter = max_iter
        self.tol = tol
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.theta = None
        self.history = {"loss": [], "acc": []}
        self.n_iter_ = 0

    def _sigmoid(self, z):
        return np.where(z >= 0,
                    1 / (1 + np.exp(-z)),
                    np.exp(z) / (1 + np.exp(z)))

    def _compute_loss(self, X, y):
        m = len(y)
        h = self._sigmoid(X @ self.theta)
        eps = 1e-10
        loss = -np.mean(y * np.log(h + eps) + (1 - y) * np.log(1 - h + eps))
        reg = self.lambda_ / (2 * m) * np.sum(self.theta[1:] ** 2)
        return loss + reg

    def _compute_accuracy(self, X, y):
        preds = (self._sigmoid(X @ self.theta) >= 0.5).astype(int)
        return np.mean(preds == y)

    def fit(self, X, y):
        m, n = X.shape
        self.theta = np.zeros(n)

        # Adam
        m_vec = np.zeros_like(self.theta)
        v_vec = np.zeros_like(self.theta)

        for it in range(1, self.max_iter + 1):
            h = self._sigmoid(X @ self.theta)
            grad = (X.T @ (h - y)) / m + (self.lambda_/m) * np.r_[0, self.theta[1:]]

            '''different optimizer'''
            if self.optimizer == 'gd':
                # Adam 一阶与二阶动量
                m_vec = self.beta1 * m_vec + (1 - self.beta1) * grad
                v_vec = self.beta2 * v_vec + (1 - self.beta2) * (grad ** 2)
                # 偏差修正
                m_hat = m_vec / (1 - self.beta1 ** it)
                v_hat = v_vec / (1 - self.beta2 ** it)
                self.theta -=  self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
                if np.linalg.norm(grad) < self.tol:
                    break
            elif self.optimizer == 'newton':
                w = h * (1 - h)
                I = np.eye(n)
                I[0, 0] = 0
                H = (1/m) * (X.T @ (w[:, None] * X)) + (self.lambda_/m) * I
                H += 1e-6 * np.eye(n)
                delta = np.linalg.solve(H, grad)
                self.theta -= delta
                if np.linalg.norm(delta) < self.tol:
                    break
            else:
                raise ValueError(f"Unknown optimizer: {self.optimizer}")

            '''Record history'''
            if it % 10 == 0 or it == self.max_iter-1:
                self.history["loss"].append(self._compute_loss(X, y))
                self.history["acc"].append(self._compute_accuracy(X, y))

        if len(self.history["acc"]) == 0:
            self.history["loss"].append(self._compute_loss(X, y))
            self.history["acc"].append(self._compute_accuracy(X, y))

        self.n_iter_ = it

    def predict(self, X):
        return (self._sigmoid(X @ self.theta) >= 0.5).astype(int)


"""utils"""
def plot_linear_data(X, y, title="Linear Separable Data"):
    X_class0 = X[y == 0]
    X_class1 = X[y == 1]

    plt.figure(figsize=(8, 6))

    plt.scatter(X_class0[:, 0], X_class0[:, 1], c='blue', marker='o', label='Class 0')
    plt.scatter(X_class1[:, 0], X_class1[:, 1], c='red', marker='s', label='Class 1')

    plt.title(title, fontsize=14)
    plt.xlabel('Feature 1', fontsize=12)
    plt.ylabel('Feature 2', fontsize=12)

    plt.legend()

    plt.grid(True, linestyle='--', alpha=0.7)

    plt.show()

def plot_loss_curve(model):
    plt.plot(model.history["loss"])
    plt.title("Loss Curve")
    plt.xlabel("Epoch (x10)")
    plt.ylabel("Loss")
    plt.show()

def plot_decision_boundary(model, X, y, scaler, title="Decision Boundary"):

    n_features = X.shape[1]

    plt.figure(figsize=(8, 6))
    x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
    y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, 200),
                         np.linspace(y_min, y_max, 200))
    grid = np.c_[xx.ravel(), yy.ravel()]

    # 保留前两维
    grid_full = np.zeros((grid.shape[0], n_features))
    grid_full[:, :2] = grid

    grid_std = scaler.transform(grid_full)
    grid_std = np.c_[np.ones(grid_std.shape[0]), grid_std]
    preds = model.predict(grid_std).reshape(xx.shape)

    plt.contourf(xx, yy, preds, cmap=plt.cm.RdBu, alpha=0.3)
    plt.scatter(X[y == 0][:, 0], X[y == 0][:, 1], c='blue', label='Class 0')
    plt.scatter(X[y == 1][:, 0], X[y == 1][:, 1], c='red', label='Class 1')
    plt.title(title)
    plt.xlabel("Feature 1")
    plt.ylabel("Feature 2")
    plt.legend()
    plt.show()

"""main function"""
def main_experiment(data_path=None, m=100, ifnaive=False):
    if data_path:
        print(f"📂 从文件加载数据: {data_path}")
        X_train, X_val, y_train, y_val, scaler = load_txt_dataset(data_path)
        X = np.vstack([X_train[:, 1:], X_val[:, 1:]])  # 用于可视化
        y = np.hstack([y_train, y_val])
    else:
        X, y = make_linear_data(n_per_class=m, naive=ifnaive)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=0)
        scaler = StandardScaler()
        X_train = np.c_[np.ones(X_train.shape[0]), scaler.fit_transform(X_train)]
        X_val   = np.c_[np.ones(X_val.shape[0]),   scaler.transform(X_val)]

    configs = [
        {"optimizer":"gd", "lambda_":0.0},
        {"optimizer":"gd", "lambda_":0.1},
        {"optimizer":"newton", "lambda_":0.0},
        {"optimizer":"newton", "lambda_":0.1},
    ]

    results = []
    for cfg in configs:
        model = LogisticRegression(**cfg)
        model.fit(X_train, y_train)
        train_acc = model.history["acc"][-1]
        final_loss = model.history["loss"][-1]
        val_acc = np.mean(model.predict(X_val) == y_val)
        results.append((cfg, train_acc, val_acc))
        print(f"Config={cfg}, Iter={model.n_iter_}, Train={train_acc:.3f}, Val={val_acc:.3f}, FinalLoss={final_loss:.4f}")

        plot_loss_curve(model)
        plot_decision_boundary(model, X, y, scaler, title=f"Decision Boundary ({cfg['optimizer']})")

if __name__ == "__main__":
    m = 200
    ifnaive = True
    # X, y = make_linear_data(n_per_class=m, naive=ifnaive)
    # plot_linear_data(X, y, "Linear Separable Data with Two Classes")

    data_path = r"..\data\data_banknote_authentication.txt"

    main_experiment(m=m, ifnaive=ifnaive)
    main_experiment(data_path=data_path, m=m, ifnaive=ifnaive)

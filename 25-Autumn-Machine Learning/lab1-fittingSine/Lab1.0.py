"""
Lab1.0.py
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional, Union, List, Dict

# ---------------------------
# 全局变量
# ---------------------------
A = 0.0
B = 2 * np.pi

# ---------------------------
# 数据生成
# ---------------------------
def generate_x(N: int, a: float = A, b: float = B) -> np.ndarray:
    """在区间 [a,b] 上均匀采样 N 个点"""
    return np.linspace(a, b, N)

def generate_y_true(x: np.ndarray) -> np.ndarray:
    """目标函数 y = sin(x)"""
    return np.sin(x)

def add_gaussian_noise(y_true: np.ndarray, sigma: float = 0.1, seed: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """在 y_true 上加入高斯噪声"""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, sigma, size=y_true.shape[0])
    return y_true + noise, noise

# ---------------------------
# 多项式基与设计矩阵
# ---------------------------
def scale_to_minus1_plus1(x: np.ndarray, a: float = A, b: float = B) -> np.ndarray:
    """将 x 映射到 [-1,1] 区间"""
    return (2 * x - (a + b)) / (b - a)

def design_matrix(x_scaled: np.ndarray, degree: int) -> np.ndarray:
    """构造 Vandermonde 设计矩阵 [1, x, x^2, ..., x^degree]"""
    return np.vander(x_scaled, N=degree + 1, increasing=True)

# ---------------------------
# 损失函数、梯度、解法
# ---------------------------
def mse_loss(X: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float = 0.0) -> float:
    """均方误差 + L2 正则化"""
    resid = y - X @ w
    loss = np.mean(resid ** 2)
    # L2 正则化
    if lam > 0:
        loss += lam * np.sum(w[1:] ** 2)
    return loss


def gradient(X: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float = 0.0) -> np.ndarray:
    """计算梯度"""
    N = X.shape[0]
    resid = y - X @ w
    grad = -(2.0 / N) * (X.T @ resid)
    # L2 正则化
    if lam > 0:
        grad[1:] += 2.0 * lam * w[1:]
    return grad


def gradient_descent(X: np.ndarray,
                     y: np.ndarray,
                     lam: float = 0.0,
                     lr: float = 1e-2,
                     max_iter: int = 10000,
                     tol_delta: float = 1e-8,
                     tol_w: float = 1e-6,
                     record_every: int = 100,
                     method: str = "adam",
                     beta1: float = 0.9,
                     beta2: float = 0.999,
                     eps: float = 1e-8) -> Tuple[np.ndarray, np.ndarray, int]:
    """批量梯度下降"""
    w = np.zeros(X.shape[1])
    loss_hist = []

    # Adam 初始化
    m = np.zeros_like(w)
    v = np.zeros_like(w)

    for it in range(1, max_iter + 1):
        grad = gradient(X, y, w, lam=lam)

        if method.lower() == "adam":
            # Adam 一阶与二阶动量
            m = beta1 * m + (1 - beta1) * grad
            v = beta2 * v + (1 - beta2) * (grad ** 2)
            # 偏差修正
            m_hat = m / (1 - beta1 ** it)
            v_hat = v / (1 - beta2 ** it)
            w_new = w - lr * m_hat / (np.sqrt(v_hat) + eps)
        else:
            # 标准梯度下降
            w_new = w - lr * grad

        if it == 1 or (record_every > 0 and it % record_every == 0):
            loss_hist.append(mse_loss(X, y, w_new, lam))

        curr_delta = np.linalg.norm(w_new - w)
        curr_w =  np.linalg.norm(grad)

        real_delta = curr_delta / (1.0 + curr_delta)
        real_w = curr_w / (1.0 + curr_w)

        if  (real_delta < tol_delta) and (real_w < tol_w):
            # print(f"now norm of w is {real_w}")
            break
        w = w_new

    return w, np.array(loss_hist), it

def ridge_closed_form(X: np.ndarray, y: np.ndarray, lam: float = 0.0) -> np.ndarray:
    """Ridge 回归解析解"""
    N, d = X.shape
    R = np.eye(d); R[0, 0] = 0.0  # 不正则化偏置
    lhs = X.T @ X + N * lam * R
    rhs = X.T @ y
    try:
        w = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        w, *_ = np.linalg.lstsq(lhs, rhs, rcond=None)
    return w


def conjugate_gradient(A: np.ndarray, b: np.ndarray, x0: Optional[np.ndarray] = None,
                       tol: float = 1e-8, max_iter: Optional[int] = None) -> Tuple[np.ndarray, int]:
    """共轭梯度法"""
    n = b.size
    if max_iter is None:
        max_iter = n
    x = np.zeros_like(b) if x0 is None else x0.copy()
    r = b - A @ x
    p = r.copy()
    rs_old = r @ r
    if rs_old == 0:
        return x, 0
    for i in range(max_iter):
        Ap = A @ p
        denom = p @ Ap
        if denom == 0:
            # 避免除零（数值退化）
            break
        alpha = rs_old / denom
        x += alpha * p
        r -= alpha * Ap
        rs_new = r @ r
        if np.sqrt(rs_new) < tol:
            return x, i + 1
        beta = rs_new / rs_old
        p = r + beta * p
        rs_old = rs_new
    return x, cg_iter


# ---------------------------
# 绘图函数
# ---------------------------
def plot_fit(x: np.ndarray, y: np.ndarray,
             w_cf: np.ndarray, w_gd: np.ndarray, w_cg: np.ndarray,
             gd_iter: int, cg_iter: int,
             degree: int, title: str = "", savepath: Optional[str] = None):
    """绘制三种方法的拟合曲线"""
    x_plot = np.linspace(A, B, 400)
    Phi_plot = design_matrix(scale_to_minus1_plus1(x_plot), degree)

    fig, axes = plt.subplots(2, 1, figsize=(6, 10))

    # ---------- Gradient Descent ----------
    ax = axes[0]
    ax.scatter(x, y, c="r", label="Training data")
    ax.plot(x_plot, np.sin(x_plot), linestyle="--", label="True sin(x)")
    ax.plot(x_plot, Phi_plot @ w_gd, label=f"Gradient Descent fit (iter={gd_iter})")
    ax.set_title("Gradient Descent")
    ax.grid(True)
    ax.set_ylim(-2, 2)
    ax.legend()

    # ---------- Closed-form + Conjugate Gradient ----------
    ax = axes[1]
    ax.scatter(x, y, c="r", label="Training data")
    ax.plot(x_plot, np.sin(x_plot), linestyle="--", label="True sin(x)")
    ax.plot(x_plot, Phi_plot @ w_cf, label="Closed-form fit")
    ax.plot(x_plot, Phi_plot @ w_cg, label=f"Conjugate Gradient fit (iter={cg_iter})")
    ax.set_title("Closed-form and Conjugate Gradient")
    ax.grid(True)
    ax.set_ylim(-2, 2)
    ax.legend()

    fig.suptitle(title)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    if savepath:
        fig.savefig(savepath, dpi=200)
    plt.show()


def plot_fit_single(x: np.ndarray, y: np.ndarray,
             w_gd: np.ndarray, gd_iter: int,
             degree: int, title: str = "", savepath: Optional[str] = None):
    """绘制单个拟合曲线"""
    x_plot = np.linspace(A, B, 400)
    Phi_plot = design_matrix(scale_to_minus1_plus1(x_plot), degree)

    fig, ax = plt.subplots(figsize=(6, 5))

    # ---------- Gradient Descent ----------
    ax.scatter(x, y, c="r", label="Training data")
    ax.plot(x_plot, np.sin(x_plot), linestyle="--", label="True sin(x)")
    ax.plot(x_plot, Phi_plot @ w_gd, label=f"Gradient Descent fit (iter={gd_iter})")
    ax.set_title("Gradient Descent")
    ax.grid(True)
    ax.set_ylim(-2, 2)
    ax.legend()

    fig.suptitle(title)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    if savepath:
        fig.savefig(savepath, dpi=200)
    plt.show()


def plot_loss_curve(loss_history: np.ndarray, iter_history: np.ndarray, record_every: int, title: str = "Training Loss"):
    """绘制梯度下降损失曲线"""
    plt.figure(figsize=(6,4))
    plt.plot(iter_history, loss_history, marker="o")
    plt.xlabel("Iteration")
    plt.ylabel("Loss")
    plt.title(title)
    plt.grid(True)
    plt.show()


# ---------------------------
# 主实验流程
# ---------------------------
def main_experiment(N: int = 10, degree: int = 6, lam: float = 1e-3, sigma: float = 0.2, gd_max_iter: int = 5000):
    seed = 39
    # 生成数据
    x = generate_x(N)
    y_true = generate_y_true(x)
    y_noisy, _ = add_gaussian_noise(y_true, sigma=sigma, seed=seed)

    # 设计矩阵
    Phi = design_matrix(scale_to_minus1_plus1(x), degree)

    # 解析解
    w_cf = ridge_closed_form(Phi, y_noisy, lam=lam)

    # 梯度下降
    w_gd, loss_hist, gd_iter = gradient_descent(Phi, y_noisy, lam=lam, lr=1e-3,
                                       max_iter=gd_max_iter, record_every=100, method="adam")

    # 共轭梯度
    N_samples = Phi.shape[0]
    d = Phi.shape[1]
    R = np.eye(d); R[0, 0] = 0.0
    A = Phi.T @ Phi + N_samples * lam * R
    b = Phi.T @ y_noisy
    w_cg, cg_iter = conjugate_gradient(A, b, max_iter=d*5)
    print(f"N={N},degree={degree},cg_iter:{cg_iter}")

    title = f"N={N}, degree={degree}, λ={lam}, σ={sigma}"
    plot_fit(x, y_noisy, w_cf, w_gd, w_cg, gd_iter, cg_iter, degree=degree, title=title, savepath=None)
    # plot_fit_single(x, y_noisy, w_gd, gd_iter, degree=degree, title=title, savepath=None)

    # 绘制损失曲线
    # plot_loss_curve(loss_hist, iter_hist, record_every=100, title="GD Training Loss")

# ---------------------------
# 运行实验
# ---------------------------
if __name__ == "__main__":

    Ns = [10,15]
    degrees = [11]
    lambdas = [0.0,1e-3]
    gd_max_iters = [500000]
    for N in Ns:
        for degree in degrees:
            for lam in lambdas:
                for gd_max_iter in gd_max_iters:
                    main_experiment(N=N, degree=degree, lam=lam, sigma=0.3, gd_max_iter=gd_max_iter)



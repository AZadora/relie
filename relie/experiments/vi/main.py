"""
Simple example of Variational Inference.

We have known data X_0 (in a Linear G space).
We observe some single X that is generated by G_0(X_0) by unknown G_0.
We have given likelihood model:
p(X|G) = N(X | G(X_0), sigma)

Now we do VI to infer p(G|X), so we optimise the ELBO:
for variational family q(G) and uniform prior:

E_{G \sim q) \log p(X|G) - log q(G)


A couple of geometries are studied.
Variational distribution is either flow (restricted to <pi) or Gaussian.

Loss is symmetry invariant loss function.
"""
import math
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn.decomposition import PCA

import torch
import torch.nn as nn

from relie.utils.experiment import print_log_summary
from relie.experiments.vi.flow_distribution import Flow, FlowDistribution
from relie.experiments.vi.pushed_gaussian_distribution import PushedGaussianDistribution
from relie.lie_distr import SO3Prior
from relie.utils.so3_tools import so3_log, so3_vee
from relie.geometry import cyclic_coordinates, invariant_loss, cyclic_permutations, rotation_matrices

torch.manual_seed(0)

# Ranodm pointcloud
# x_zero = torch.randn(100, 3, dtype=torch.double)
# symmetry = torch.eye(3)[None].double()


# Two points
# x_zero = torch.tensor(cyclic_coordinates(2)).double()
# symmetry = rotation_matrices(cyclic_coordinates(2), cyclic_permutations(2))

# Equilateral triangle
x_zero = torch.tensor(cyclic_coordinates(3)).double()
symmetry = rotation_matrices(cyclic_coordinates(2), cyclic_permutations(2))

g_zero = SO3Prior(dtype=torch.double).sample((1,))[0]
# g_zero = torch.eye(3, dtype=torch.double)
g_zero_alg = so3_vee(so3_log(g_zero))
x = (g_zero @ x_zero.t()).t()


symmetry = torch.tensor(symmetry).double()


def prediction_loss_fn(g, x, x_zero):
    """
    Prediction loss = -log p(X|G)
    Allows for batching in G.
    :param g: Group shape (b, 3, 3)
    :param x: (n, 3)
    :param x_zero: (n, 3)
    :return: (b)
    """
    y = torch.einsum('bij,nj->bni', [g, x_zero])  # [b, n, 3]
    x = x.expand_as(y)
    l = invariant_loss(x.contiguous(), y.contiguous(), symmetry)
    return l.mean(1)


class VIModel(nn.Module):
    def __init__(self, distr):
        super().__init__()
        self.distr = distr
        self.beta = 1E-1

    def forward(self, x, x_zero):
        distr = self.distr()
        g = distr.rsample((64,))

        prediction_loss = prediction_loss_fn(g, x, x_zero).float()
        entropy = -distr.log_prob(g)
        loss = prediction_loss - entropy * self.beta
        return loss, {
            'loss': loss.mean().item(),
            'prediction': prediction_loss.mean().item(),
            'entropy': entropy.mean().item(),
        }


def plot_group_samples(model):
    model.eval()
    num_noise_samples = 1000
    inferred_distr = model.distr()
    inferred_samples = inferred_distr.sample((num_noise_samples, )).view(-1, 9)
    pca = PCA(3).fit(inferred_samples)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(*pca.transform(inferred_samples).T, label="Model samples", alpha=.1)
    ax.view_init(70, 30)
    # plt.legend()
    plt.show()


flow = Flow(3, 12, batch_norm=False)
flow_distr = FlowDistribution(flow, math.pi * 1.0)
gaussian_distr = PushedGaussianDistribution(lie_multiply=True)
# model = VIModel(gaussian_distr)
model = VIModel(flow_distr)
optimizer = torch.optim.Adam(model.parameters(), lr=1E-3)

infos = []
for it in range(50000):
    model.train()
    # with torch.autograd.detect_anomaly():
    loss, info = model(x, x_zero)
    optimizer.zero_grad()
    loss.mean().backward()
    optimizer.step()
    infos.append(info)

    for n, p in model.named_parameters():
        assert torch.isnan(p).sum() == 0, f"NaN in parameters {n}"

    if it % 1000 == 0:
        print_log_summary(it, 1000, infos)
        plot_group_samples(model)
        if model.distr is gaussian_distr:
            print(f"Parameters: {torch.cat([gaussian_distr.loc, gaussian_distr.scale]).tolist()}")
            print(f"Target at {g_zero_alg.tolist()}")


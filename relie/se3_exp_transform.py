import math

import torch
from relie import LocalDiffeoTransform
from relie.utils.se3_tools import se3_exp, se3_log, se3_log_abs_det_jacobian, se3_xset
from torch.distributions import Transform, constraints


class SE3ExpTransform(LocalDiffeoTransform):
    domain = constraints.real
    codomain = constraints.real

    event_dim = 1

    def __init__(self, k_max=5):
        """
        :param k_max: Returns inverse set with k in [-k_max, k_max]
        """
        super().__init__()
        self.k_max = k_max

    def _call(self, x):
        return se3_exp(x)

    def _inverse_set(self, y):
        return self._xset(se3_log(y))

    def _xset(self, x):
        xset = se3_xset(x, self.k_max)
        mask = torch.full(xset.shape[:-1], True, dtype=torch.bool, device=x.device)
        return x, xset, mask

    def log_abs_det_jacobian(self, x, y):
        """
        Log abs det of forward jacobian of exp map.
        :param x: Algebra element shape (..., 3)
        :param y: Group element (..., 3, 3)
        :return: Jacobian of exp shape (...)
        """
        return se3_log_abs_det_jacobian(x).float()


class SE3ExpCompactTransform(LocalDiffeoTransform):
    """Assumes underlying distribution has support only in the <2pi ball."""

    domain = constraints.real
    codomain = constraints.real

    event_dim = 1

    def __init__(self, support_radius=2 * math.pi):
        """
        :param support_radius: radius of inverse set.
        """
        super().__init__()
        self.support_radius = support_radius

    def _call(self, x):
        return se3_exp(x)

    def _inverse_set(self, y):
        return self._xset(se3_log(y))

    def _xset(self, x):
        xset = se3_xset(x, 1)
        norms = xset[...,:3].norm(dim=-1)
        mask = norms < self.support_radius
        xset = xset.masked_fill_(~mask[..., None], 0)
        return x, xset, mask

    def log_abs_det_jacobian(self, x, y):
        """
        Log abs det of forward jacobian of exp map.
        :param x: Algebra element shape (..., 3)
        :param y: Group element (..., 3, 3)
        :return: Jacobian of exp shape (...)
        """
        return se3_log_abs_det_jacobian(x).float()


class SE3ExpBijectiveTransform(Transform):
    """Assumes underlying distribution has support only in the <pi ball."""

    domain = constraints.real
    codomain = constraints.real

    event_dim = 1

    def __init__(self):
        super().__init__(1)

    def _call(self, x):
        return se3_exp(x)

    def _inverse(self, y):
        return se3_log(y)

    def log_abs_det_jacobian(self, x, y):
        """
        Log abs det of forward jacobian of exp map.
        :param x: Algebra element shape (..., 3)
        :param y: Group element (..., 3, 3)
        :return: Jacobian of exp shape (...)
        """
        return se3_log_abs_det_jacobian(x).float()

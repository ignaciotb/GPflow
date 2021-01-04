# Copyright 2017-2020 The GPflow Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import tensorflow as tf

from ..config import default_float
from ..inducing_variables import InducingPatches, InducingPoints, Multiscale
from ..kernels import Convolutional, Kernel, SquaredExponential
from .dispatch import Kuu


@Kuu.register(InducingPoints, Kernel)
def Kuu_kernel_inducingpoints(inducing_variable: InducingPoints, kernel: Kernel, *, jitter=0.0):
    Kzz = kernel(inducing_variable.Z)
    Kzz += jitter * tf.eye(inducing_variable.num_inducing, dtype=Kzz.dtype)
    return Kzz


def Kss(inducing_variable, CovX):
    """ 
    :param inducing_variable: inducing_variable: list of indices into the columns of X.
    :param CovX: full covariance of prior p(X)
    """
    d = np.size(inducing_variable.Z, 0) # Dim of latent variables P
    Xs = np.array(inducing_variable, dtype=int)
    
    # Allocate output
    Kzz = np.zeros((len(Xs)*d, len(Xs)*d))

    # TODO: try to get rid of nested for loops
    cnt = 0
    for i in Xs:
        # Diagonal terms
        Kzz[cnt*d:cnt*d+d, cnt*d:cnt*d+d] = CovX[i*d:i*d + d, i*d:i*d+d]
        # Off-diagonal terms 
        cnt_j = cnt+1
        for j in Xs[cnt_j:]:
            Kzz[cnt*d:cnt*d+d, cnt_j*d:cnt_j*d+d] = CovX[i*d:i*d + d, j*d:j*d+d]
            Kzz[cnt_j*d:cnt_j*d+d, cnt*d:cnt*d+d] = CovX[i*d:i*d + d, j*d:j*d+d].T
            cnt_j += 1
        cnt += 1

    return Kzz

@Kuu.register(Multiscale, SquaredExponential)
def Kuu_sqexp_multiscale(inducing_variable: Multiscale, kernel: SquaredExponential, *, jitter=0.0):
    Zmu, Zlen = kernel.slice(inducing_variable.Z, inducing_variable.scales)
    idlengthscales2 = tf.square(kernel.lengthscales + Zlen)
    sc = tf.sqrt(
        idlengthscales2[None, ...] + idlengthscales2[:, None, ...] - kernel.lengthscales ** 2
    )
    d = inducing_variable._cust_square_dist(Zmu, Zmu, sc)
    Kzz = kernel.variance * tf.exp(-d / 2) * tf.reduce_prod(kernel.lengthscales / sc, 2)
    Kzz += jitter * tf.eye(inducing_variable.num_inducing, dtype=Kzz.dtype)
    return Kzz


@Kuu.register(InducingPatches, Convolutional)
def Kuu_conv_patch(inducing_variable, kernel, jitter=0.0):
    return kernel.base_kernel.K(inducing_variable.Z) + jitter * tf.eye(
        inducing_variable.num_inducing, dtype=default_float()
    )

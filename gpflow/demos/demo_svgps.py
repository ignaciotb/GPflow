

import numpy as np
import gpflow
import tensorflow as tf
import matplotlib.pyplot as plt
from gpflow.utilities import print_summary

plt.style.use('ggplot')





#=================================================================================================


# rho ~ f1(x1)f2(x2) + f3(x3)

# paradigm parameters
n = 500; # number of observations
observations = 'poisson';  #'binomial';
xrange1 =[0, 2];
f1_ = lambda x: np.exp(x / 2);
xrange2 = [0, 2];
f2_ = lambda x: 1 + np.cos(x + np.pi / 6)** 2;
xrange3 =[0, 2];

f1 = lambda x: f1_(x)/f1_(0)
f2 = lambda x: f2_(x)/f2_(0)

f3 = lambda x: -np.sin(x);
fs = [f1, f2, f3]
xranges = [xrange1, xrange2, xrange3]
# generate input variables (from uniform distribution in defined range)

C = len(fs)
X = np.zeros((n, C))
for c in range(3):
    X[:, c] = xranges[c][0] + np.random.rand(n,) * np.diff(xranges[0])

# generate response

rho = (f1(X[:, 0]) * f2(X[:, 1]) + f3(X[:, 2]))[..., None]; # predictor
F = np.vstack([fs[c](X[:, c]) for c in range(C)]).T


phi = lambda x:1. / (1 + np.exp(-x))
if observations == 'binomial':
    pval = phi(rho); # pass through sigmoid
    Y = (pval > np.random.rand(n, 1)).astype(float); # generate response from Bernoulli distribution
elif observations == 'poisson':
    Y = np.random.poisson(np.exp(rho)).astype(float)

N, C = X.shape
data = (X, Y)
print(X.shape, Y.shape)
#=================================================================================================


cols = 'rgb'
#C = 2

# ## Building the model

from gpflow.kernels import SquaredExponential, Conditioned
kernels = [
    Conditioned(SquaredExponential(), [np.zeros((1, 1)), np.ones((1, 1))]),
    Conditioned(SquaredExponential(), [np.zeros((1, 1)), np.ones((1, 1))]),
    SquaredExponential()
]

from gpflow.mean_functions import ConditionedMeanFunction, Zero
mean_functions = [
    ConditionedMeanFunction(kernels[0]),
    ConditionedMeanFunction(kernels[1]),
    Zero()
]

indices = [slice(c,c+1) for c in range(C)]

Zs = [X[::5, c][..., None].copy() for c in range(C)]

q_mus = [
np.ones((len(Zs[0]), 1)),
np.ones((len(Zs[1]), 1)),
np.zeros((len(Zs[2]), 1)),
]

if observations == 'binomial':
    likelihood = gpflow.likelihoods.Bernoulli()
elif observations == 'poisson':
    likelihood = gpflow.likelihoods.Poisson()

m = gpflow.models.Custom(kernels, likelihood, Zs, indices, num_data=N,
                        deterministic_optimisation=False,
                         mean_functions=mean_functions)

log_likelihood = tf.function(autograph=False)(m.log_likelihood)

# We turn off training for inducing point locations
gpflow.utilities.set_trainable(m.inducing_variables, False)


@tf.function(autograph=False)
def optimization_step(optimizer, model, batch):
    with tf.GradientTape(watch_accessed_variables=False) as tape:
        tape.watch(model.trainable_variables)
        objective = - m.elbo(batch)
        grads = tape.gradient(objective, m.trainable_variables)
    optimizer.apply_gradients(zip(grads, m.trainable_variables))
    return objective


def run_adam(model, iterations):
    """
    Utility function running the Adam optimizer

    :param model: GPflow model
    :param interations: number of iterations
    """
    # Create an Adam Optimizer action
    logf = []
    adam = tf.optimizers.Adam(learning_rate=5e-3)
    for step in range(iterations):
        elbo = - optimization_step(adam, model, data)
        if step % 10 == 0:
            logf.append(elbo.numpy())
            print(step, elbo.numpy())
    return logf

maxiter = 2000

logf = run_adam(m, maxiter)


f_means, f_vars = m.predict_fs(X)
p_mean, _ = m.predict_predictor(X)

fig, axarr = plt.subplots(2,2)
ax = axarr[0,0]
ax.plot(np.arange(maxiter)[::10], logf)
ax.set_xlabel('iteration')
ax.set_ylabel('ELBO');

ax = axarr[0,1]
for c in range(C):
    o = np.argsort(X[:, c])
    ax.plot(X[o, c], F[o, c], '-', color=cols[c], mew=2);
    ax.plot(X[:, c], f_means[:, c], '.', color=cols[c], mew=2);

ax = axarr[1,0]
ax.plot(p_mean, Y, 'b*')
ax.plot(Y, Y, 'k-', alpha=.1)
ax.set_ylabel('data y')
ax.set_xlabel('prediction');

ax = axarr[1,1]
ax.plot(p_mean, rho, 'b*')
ax.plot(rho, rho, 'k-', alpha=.1)
ax.set_ylabel('data rho')
ax.set_xlabel('prediction');
plt.show()
#
# opt = gpflow.optimizers.Scipy()
#
# def objective_closure():
#     return - m.elbo(data)
#
# mus, vars = m.predict_fs(X)
#
# print(m.elbo(data))
# print(m.num_components)
# print(m.predict_fs(X)[0].shape)
# print(m.predict_fs(X)[1].shape)
#
# with tf.GradientTape() as tape:
#     tape.watch(m.trainable_variables)
#     res = m.elbo(data)
# grads = tape.gradient(res, m.trainable_variables)
# for v, g in zip(m.trainable_variables, grads):
#     if g is None:
#         print(v, g)
#
# opt_logs = opt.minimize(objective_closure,
#                         m.trainable_variables,
#                         options=dict(maxiter=1000))

print_summary(m)




# ## generate test points for prediction
# xx = np.linspace(xmin - 0.1, xmax + 0.1, 100).reshape(100, 1)  # test points must be of shape (N, D)
#
# ## predict mean and variance of latent GP at test points
# mean, var = m.predict_f(xx)
#
# ## generate 10 samples from posterior
# samples = m.predict_f_samples(xx, 10)  # shape (10, 100, 1)
#
# ## plot
# plt.figure(figsize=(12, 6))
# plt.plot(X, Y, 'kx', mew=2)
# plt.plot(xx, mean, 'C0', lw=2)
# plt.fill_between(xx[:,0],
#                  mean[:,0] - 1.96 * np.sqrt(var[:,0]),
#                  mean[:,0] + 1.96 * np.sqrt(var[:,0]),
#                  color='C0', alpha=0.2)
#
# plt.plot(xx, samples[:, :, 0].numpy().T, 'C0', linewidth=.5)
# plt.xlim(xmin - 0.1, xmax + 0.1);
# plt.show()
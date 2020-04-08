"""
This file is a technical script to create data structures compatible with tf.function.
"""
import abc
from functools import partial

import attr
import tensorflow as tf


def _pairwise(iterable):
    """s -> (s0, s1), (s2, s3), (s4, s5), ..."""
    a = iter(iterable)
    return zip(a, a)


class Module(tf.Module, metaclass=abc.ABCMeta):
    """
    Base class for filterflow Modules - __call__ is ignored
    """

    def __call__(self, *args, **kwargs):
        pass


@attr.s(frozen=True)
class DataSeries(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def write(self, t, data_point):
        """Inferface method"""

    @abc.abstractmethod
    def read(self, t):
        """Inferface method"""

    @abc.abstractmethod
    def stack(self):
        """Inferface method"""

    @abc.abstractmethod
    def size(self):
        """Interface method"""


def _non_scalar_validator(_instance, attribute, value, ndim=None):
    if ndim is None or value is None or isinstance(value, tf.DType):
        return

    if hasattr(value, 'shape'):
        value_shape = value.shape
    elif isinstance(value, tf.TensorShape):
        value_shape = value
    else:
        raise ValueError(f"value {value} for attribute {attribute} should have an attribute shape or be a TensorShape.")
    if hasattr(value_shape, '__len__'):
        assert len(value_shape) == ndim, f"value {value} for attribute {attribute} should have ndim {ndim}."


_dim_3_validator = partial(_non_scalar_validator, ndim=3)
_dim_2_validator = partial(_non_scalar_validator, ndim=2)
_dim_1_validator = partial(_non_scalar_validator, ndim=1)


@attr.s(frozen=True)
class State:
    """Particle Filter State
    State encapsulates the information about the particle filter current state.
    """
    ADDITIONAL_STATE_VARIABLES = ()

    particles = attr.ib(validator=_dim_3_validator)
    log_weights = attr.ib(validator=_dim_2_validator)
    weights = attr.ib(validator=_dim_2_validator)
    log_likelihoods = attr.ib(validator=_dim_1_validator)

    @property
    def batch_size(self):
        return self.particles.shape[0]

    @property
    def n_particles(self):
        return self.particles.shape[1]

    @property
    def dimension(self):
        return self.particles.shape[2]


@attr.s
class StateWithMemory(State):
    ADDITIONAL_STATE_VARIABLES = ('rnn_state',)
    rnn_state = attr.ib(validator=_dim_3_validator)


@attr.s(frozen=True)
class StateSeries(DataSeries, metaclass=abc.ABCMeta):
    batch_size = attr.ib()
    n_particles = attr.ib()
    dimension = attr.ib()

    particles = attr.ib(default=None)
    log_weights = attr.ib(default=None)
    weights = attr.ib(default=None)
    log_likelihoods = attr.ib(default=None)

    DTYPE = None

    def _set_ta(self, attr, shape):
        ta = tf.TensorArray(self.DTYPE,
                            size=0,
                            dynamic_size=True, clear_after_read=False, element_shape=tf.TensorShape(shape))
        object.__setattr__(self, attr, ta)

    def __attrs_post_init__(self):
        # particles
        particles_shape = [self.batch_size, self.n_particles, self.dimension]
        if self.particles is None:
            self._set_ta('particles', particles_shape)

        # weights
        weights_shape = [self.batch_size, self.n_particles]
        if self.weights is None:
            self._set_ta('weights', weights_shape)

        # log_weights
        log_weights_shape = [self.batch_size, self.n_particles]
        if self.log_weights is None:
            self._set_ta('log_weights', log_weights_shape)

        # log_likelihoods
        log_lik_shape = [self.batch_size]
        if self.log_likelihoods is None:
            self._set_ta('log_likelihoods', log_lik_shape)

    def write(self, t, state):
        particles = self.particles.write(t, state.particles)
        log_weights = self.log_weights.write(t, state.log_weights)
        weights = self.weights.write(t, state.weights)
        log_likelihoods = self.log_likelihoods.write(t, state.log_likelihoods)
        return attr.evolve(self, particles=particles, log_weights=log_weights, weights=weights,
                           log_likelihoods=log_likelihoods)

    def stack(self):
        particles = self.particles.stack()
        log_weights = self.log_weights.stack()
        weights = self.weights.stack()
        log_likelihoods = self.log_likelihoods.stack()
        return attr.evolve(self, particles=particles, log_weights=log_weights, weights=weights,
                           log_likelihoods=log_likelihoods)

    def size(self):
        if isinstance(self.particles, tf.TensorArray):
            return self.particles.size()
        else:
            return self.particles.shape[0]

    def read(self, t):
        if isinstance(self.particles, tf.TensorArray):
            particles = self.particles.read(t)
            log_weights = self.log_weights.read(t)
            weights = self.weights.read(t)
            log_likelihoods = self.log_likelihoods.read(t)
        else:
            particles = self.particles[t]
            log_weights = self.log_weights[t]
            weights = self.weights[t]
            log_likelihoods = self.log_likelihoods[t]

        state = State(particles=particles,
                      log_weights=log_weights,
                      weights=weights,
                      log_likelihoods=log_likelihoods)
        return state


@attr.s(frozen=True)
class FloatStateSeries(StateSeries):
    DTYPE = tf.dtypes.float32


@attr.s(frozen=True)
class DoubleStateSeries(StateSeries):
    DTYPE = tf.dtypes.float64


DTYPE_TO_STATE_SERIES = {klass.DTYPE: klass for klass in StateSeries.__subclasses__()}


@attr.s(frozen=True)
class Observation:
    observation = attr.ib(validator=_non_scalar_validator)

    @property
    def shape(self):
        return self.observation.shape


@attr.s(frozen=True)
class ObservationSeries(DataSeries, metaclass=abc.ABCMeta):
    DTYPE = None

    shape = attr.ib()
    _observation = attr.ib(default=None)

    @property
    def observation(self):
        return self._observation

    def __attrs_post_init__(self):
        if self._observation is None:
            ta = tf.TensorArray(self.DTYPE,
                                size=0,
                                dynamic_size=True,
                                clear_after_read=False,
                                tensor_array_name='ObservationSeries',
                                element_shape=tf.TensorShape(self.shape))
            object.__setattr__(self, '_observation', ta)

    def write(self, t, observation):
        observation = self._observation.write(t, tf.reshape(observation.observation, self.shape))
        return attr.evolve(self, observation=observation)

    def stack(self):
        observations = self._observation.stack()
        observations_dataset = tf.data.Dataset.from_tensor_slices(observations)
        return observations_dataset.map(Observation)

    def read(self, t):
        if isinstance(self._observation, tf.TensorArray):
            observation = self._observation.read(t)
        else:
            observation = self._observation[t]
        if isinstance(observation, Observation):
            return observation
        return Observation(observation)

    def size(self):
        if isinstance(self._observation, tf.TensorArray):
            return self._observation.size()
        else:
            return self._observation.shape[0]


@attr.s(frozen=True)
class FloatObservationSeries(ObservationSeries):
    DTYPE = tf.dtypes.float32


@attr.s(frozen=True)
class DoubleObservationSeries(ObservationSeries):
    DTYPE = tf.dtypes.float64


DTYPE_TO_OBSERVATION_SERIES = {klass.DTYPE: klass for klass in ObservationSeries.__subclasses__()}


# TODO : Have a think about what inputs we want exactly - e.g. use a dynamic classifier example to see what we need
@attr.s
class InputsBase(metaclass=abc.ABCMeta):
    """Container interface to implement an arbitrary collection of inputs to give to the filter at time of prediction
    """

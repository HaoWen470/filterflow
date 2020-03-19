import abc

import tensorflow as tf

from filterflow.base import State, ObservationBase


class ObservationModelBase(tf.Module, metaclass=abc.ABCMeta):
    @tf.function
    def loglikelihood(self, state: State, observation: ObservationBase):
        """Computes the loglikelihood of an observation given proposed particles
        :param state: State
            Proposed (predicted) state of the filter given State at t-1 and Observation
        :param observation: ObservationBase
            User/Process given observation
        :return: a tensor of loglikelihoods for all particles
        :rtype: tf.Tensor
        """
        return self._loglikelihood(state.particles, observation)

    @abc.abstractmethod
    @tf.function
    def _loglikelihood(self, particles: tf.Tensor, observation: ObservationBase):
        """User defined implementation
        :param particles: tf.Tensor
            Particles from State
        :param observation: ObservationBase
            User given observation
        :return: tf.Tensor
        """

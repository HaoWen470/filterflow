from contextlib import contextmanager

import numpy as np
import tensorflow as tf

from filterflow.base import Observation, State, FloatStateSeries, StateSeries, FloatObservationSeries, ObservationSeries


class TestBaseClasses(tf.test.TestCase):
    @contextmanager
    def assertNoLogs(self):
        with self.assertRaises(AssertionError) as a:
            with self.assertLogs() as b:
                yield (a, b)

    @staticmethod
    @tf.function
    def _test_function(obj):
        return obj

    def test_test_function(self):
        # test that the test is working...

        with self.assertNoLogs():
            # We need to test it doesn't log anything
            for j in range(50):
                _ = self._test_function(tf.constant(j))

        with self.assertLogs():
            for j in range(50):
                _ = self._test_function(j)

    def test_observation(self):
        with self.assertRaises(ValueError):
            _ = Observation(0., 1)

        with self.assertRaises(ValueError):
            _ = Observation([0.], 1)

        with self.assertNoLogs():
            for i in range(20):
                observation = Observation(np.array([i]), 1)
                _ = self._test_function(observation)

    def test_state(self):
        with self.assertRaises(ValueError):
            _ = State(0., 0., 0., 0.)

        with self.assertRaises(AssertionError):
            _ = State(np.zeros([5, 5]), np.zeros([5, 5]), np.zeros([5, 5]), np.zeros([5]))
        with self.assertRaises(AssertionError):
            _ = State(np.zeros([5, 5, 1]), np.zeros([5]), np.zeros([5, 5]), np.zeros([5]))
        with self.assertRaises(AssertionError):
            _ = State(np.zeros([5, 5, 1]), np.zeros([5, 5]), np.zeros([5]), np.zeros([5]))
        with self.assertRaises(AssertionError):
            _ = State(np.zeros([5, 5, 1]), np.zeros([5, 5]), np.zeros([5, 5]), np.zeros([5, 2]))

        with self.assertNoLogs():
            state = State(np.random.uniform(0., 1., [5, 5, 1]), np.zeros([5, 5]), np.zeros([5, 5]), np.zeros([5, ]))
            self._test_function(state)

    def test_state_series(self):
        @tf.function
        def fun(state):
            float_state_series = FloatStateSeries(batch_size=5, n_particles=10,
                                                  dimension=2)
            for i in tf.range(10):
                float_state_series = float_state_series.write(i, state)
            return float_state_series.stack()

        particles = np.random.uniform(0., 1., [5, 10, 2]).astype(np.float32)
        weights = np.random.uniform(0., 1., [5, 10]).astype(np.float32)
        log_weights = np.random.uniform(0., 1., [5, 10]).astype(np.float32)
        log_likelihoods = np.random.uniform(0., 1., [5]).astype(np.float32)
        state = State(particles, log_weights, weights, log_likelihoods)

        res = fun(state)
        self.assertIsInstance(res, StateSeries)
        self.assertIsInstance(res.read(5), State)

    def test_observation_series(self):
        @tf.function
        def fun(obs):

            observation_series = FloatObservationSeries([1, 1, 1])
            for i in tf.range(10):
                observation_series = observation_series.write(i, obs)
            return observation_series.stack()

        obs = Observation(np.zeros([1, 1, 1], dtype=np.float32))

        res = fun(obs)
        self.assertIsInstance(res, ObservationSeries)
        self.assertIsInstance(res.read(5), Observation)
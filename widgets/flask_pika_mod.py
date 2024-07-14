# From flask-pika, https://github.com/wdtinc/flask-pika, with little modification

import datetime
import pika
from pika import connection

# python-3 compatibility
try:
    from Queue import Queue
except ImportError as e:
    from queue import Queue

try:
    xrange
except NameError as e:
    xrange = range

__all__ = ['Pika']


class Pika(object):

    def __init__(self, app=None):
        """
            Create the Flask Pika extension.
        """
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
            Initialize the Flask Pika extension
        """
        pika_params = app.config['FLASK_PIKA_PARAMS']
        pool_params = app.config['FLASK_PIKA_POOL_PARAMS']

        self.debug = app.debug
        self.logger = app.logger
        self.pool_size = 1
        self.pool_recycle = -1
        self.pool_queue = Queue()
        self.channel_recycle_times = {}

        # fix create credentials if needed
        if isinstance(pika_params, connection.Parameters):
            self._pika_connection_params = pika_params
        else:
            if 'credentials' not in pika_params:
                pika_params['credentials'] = pika.PlainCredentials(pika_params['username'], pika_params['password'])
                del pika_params['username']
                del pika_params['password']
            self._pika_connection_params = pika.ConnectionParameters(**pika_params)

        self.__DEBUG("Connection params are %s" % self._pika_connection_params)

        # setup pooling if requested
        if pool_params is not None:
            self.pool_size = pool_params['pool_size']
            self.pool_recycle = pool_params['pool_recycle']
            for i in xrange(self.pool_size):
                channel = PrePopulationChannel()
                self.__set_recycle_for_channel(channel, -1)
                self.pool_queue.put(channel)
            self.__DEBUG("Pool params are %s" % pool_params)

    def __create_channel(self):
        """
            Create a connection and a channel based on pika params
        """
        pika_connection = pika.BlockingConnection(self._pika_connection_params)
        channel = pika_connection.channel()
        self.__DEBUG("Created AMQP Connection and Channel %s" % channel)
        self.__set_recycle_for_channel(channel)
        return channel

    def __destroy_channel(self, channel):
        """
            Destroy a channel by closing it's underlying connection
        """
        self.__remove_recycle_time_for_channel(channel)
        try:
            channel.connection.close()
            self.__DEBUG("Destroyed AMQP Connection and Channel %s" % channel)
        except Exception as e:
            self.__WARN("Failed to destroy channel cleanly %s" % e)

    def __set_recycle_for_channel(self, channel, recycle_time=None):
        """
            Set the next recycle time for a channel
        """
        if recycle_time is None:
            recycle_time = (unix_time_millis_now() + (self.pool_recycle * 1000))

        self.channel_recycle_times[hash(channel)] = recycle_time

    def __remove_recycle_time_for_channel(self, channel):
        """
            Remove the recycle time for a given channel if it exists
        """
        channel_hash = hash(channel)
        if channel_hash in self.channel_recycle_times:
            del self.channel_recycle_times[channel_hash]

    def __should_recycle_channel(self, channel):
        """
            Determine if a channel should be recycled based on it's recycle time
        """
        recycle_time = self.channel_recycle_times[hash(channel)]
        return recycle_time < unix_time_millis_now()

    def channel(self):
        """
            Get a channel
            If pooling is setup, this will block until a channel is available
            If pooling is not setup, a new channel will be created
        """
        # if using pooling
        if self.pool_recycle > -1:
            # get channel from pool or block until channel is available
            ch = self.pool_queue.get()
            self.__DEBUG("Got Pika channel from pool %s" % ch)

            # recycle channel if needed or extend recycle time
            if self.__should_recycle_channel(ch):
                old_channel = ch
                self.__destroy_channel(ch)
                ch = self.__create_channel()
                self.__DEBUG(
                    "Pika channel is too old, recycling channel %s and replacing it with %s" % (old_channel, ch))
            else:
                self.__set_recycle_for_channel(ch)

            # make sure our channel is still open
            while ch is None or not ch.is_open:
                old_channel = ch
                self.__destroy_channel(ch)
                ch = self.__create_channel()
                self.__WARN("Pika channel not open, replacing channel %s with %s" % (old_channel, ch))

        # if not using pooling
        else:
            # create a new channel
            ch = self.__create_channel()

        # add support context manager
        def close():
            self.return_channel(ch)

        return ProxyContextManager(instance=ch, close_callback=close)

    def return_channel(self, channel):
        """
            Return a channel
            If pooling is setup, will return the channel to the channel pool
                **unless** the channel is closed, then channel is passed to return_broken_channel
            If pooling is not setup, will destroy the channel
        """
        # if using pooling
        if self.pool_recycle > -1:
            self.__DEBUG("Returning Pika channel to pool %s" % channel)
            if channel.is_open:
                self.pool_queue.put(channel)
            else:
                self.return_broken_channel(channel)

        # if not using pooling then just destroy the channel
        else:
            self.__destroy_channel(channel)

    def return_broken_channel(self, channel):
        """
            Return a broken channel
            If pooling is setup, will destroy the broken channel and replace it in the channel pool with a new channel
            If pooling is not setup, will destroy the channel
        """
        # if using pooling
        if self.pool_recycle > -1:
            self.__WARN("Pika channel returned in broken state, replacing %s" % channel)
            self.__destroy_channel(channel)
            self.pool_queue.put(self.__create_channel())

        # if not using pooling then just destroy the channel
        else:
            self.__WARN("Pika channel returned in broken state %s" % channel)
            self.__destroy_channel(channel)

    def __DEBUG(self, msg):
        """
            Log a message at debug level if app in debug mode
        """
        if self.debug:
            self.logger.debug(msg)

    def __WARN(self, msg):
        """
            Log a message at warning level
        """
        self.logger.warn(msg)


class PrePopulationChannel(object):

    def __init__(self):
        self._connection = PrePopulationConnection()

    @property
    def connection(self):
        return self._connection


class PrePopulationConnection(object):

    def __init__(self):
        pass

    def close(self):
        pass


def unix_time(dt):
    """
        Return unix time in microseconds
    """
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return int((delta.microseconds + (delta.seconds + delta.days * 24 * 3600) * 10 ** 6) / 10 ** 6)


def unix_time_millis(dt):
    """
        Return unix time in milliseconds
    """
    return round(unix_time(dt) * 1000.0)


def unix_time_millis_now():
    """
        Return current unix time in milliseconds
    """
    return unix_time_millis(datetime.datetime.utcnow())


class ProxyContextManager(object):
    """
        working as proxy object or as context manager for object
    """

    def __init__(self, instance, close_callback=None):
        self.instance = instance
        self.close_callback = close_callback

    def __getattr__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            return getattr(self.instance, key)

    def __enter__(self):
        return self.instance

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.close_callback:
            self.close_callback()
        else:
            self.instance.close()

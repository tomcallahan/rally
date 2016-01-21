import socket
import elasticsearch
import logging

from enum import Enum

import rally.time


class ClusterStatus(Enum):
  red = 1
  yellow = 2
  green = 3


logger = logging.getLogger("rally.cluster")


class Server:
  def __init__(self, process, telemetry):
    self._process = process
    self._telemetry = telemetry

  @property
  def process(self):
    return self._process

  @property
  def telemetry(self):
    return self._telemetry

  def on_benchmark_start(self):
    self._telemetry.on_benchmark_start()

  def on_benchmark_stop(self):
    self._telemetry.on_benchmark_stop()


class Cluster:
  """
  Cluster exposes APIs of the running benchmark candidate.
  """

  def __init__(self, servers, metrics_store, clock=rally.time.Clock):
    self._es = elasticsearch.Elasticsearch()
    self._servers = servers
    self._metrics_store = metrics_store
    self._clock = clock

  @property
  def servers(self):
    return self._servers

  @property
  def client(self):
    return self._es

  @property
  def metrics_store(self):
    return self._metrics_store

  def wait_for_status(self, cluster_status):
    cluster_status_name = cluster_status.name
    logger.info('\nWait for %s cluster...' % cluster_status_name)
    es = self._es
    stop_watch = self._clock.stop_watch()
    stop_watch.start()
    while True:
      try:
        result = es.cluster.health(wait_for_status=cluster_status_name, wait_for_relocating_shards=0, timeout='1s')
      except (socket.timeout, elasticsearch.exceptions.ConnectionError, elasticsearch.exceptions.TransportError):
        pass
      else:
        logger.info('GOT: %s' % str(result))
        logger.info('ALLOC:\n%s' % es.cat.allocation(v=True))
        logger.info('RECOVERY:\n%s' % es.cat.recovery(v=True))
        logger.info('SHARDS:\n%s' % es.cat.shards(v=True))
        if result['status'] == cluster_status_name and result['relocating_shards'] == 0:
          break
        else:
          rally.time.sleep(0.5)

    stop_watch.stop()
    logger.info('%s cluster done (%.1f sec)' % (cluster_status_name, stop_watch.total_time()))
    logger.info('Cluster health: %s' % str(es.cluster.health()))
    logger.info('SHARDS:\n%s' % es.cat.shards(v=True))

  def on_benchmark_start(self):
    for server in self._servers:
      server.on_benchmark_start()

  def on_benchmark_stop(self):
    for server in self._servers:
      server.on_benchmark_stop()

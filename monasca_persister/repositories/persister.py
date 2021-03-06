# (C) Copyright 2016 Hewlett Packard Enterprise Development Company LP
# (C) Copyright 2017 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os

from oslo_config import cfg
from oslo_log import log

from monasca_common.confluent_kafka import consumer

LOG = log.getLogger(__name__)


class Persister(object):

    def __init__(self, kafka_conf, zookeeper_conf, repository):
        
        LOG.info("enter init:")
        self._data_points = []

        self._kafka_topic = kafka_conf.topic

        self._batch_size = kafka_conf.batch_size

        def print_assignment(consumer, partitions):
            print('Assignment:', partitions)
        
        self._consumer = consumer.KafkaConsumer(
            kafka_conf.uri,
            kafka_conf.group_id,
            kafka_conf.topic,
            self._batch_size,
            repartition_callback=self._flush,
            commit_callback=self._flush,max_commit_interval=kafka_conf.max_wait_time_seconds)
        LOG.info("after consumer:")
        self.repository = repository()

    def _flush(self):
        print("enter flush:")
        LOG.info("enter flush:")
        if not self._data_points:
            return

        try:
            self.repository.write_batch(self._data_points)

            LOG.info("Processed {} messages from topic '{}'".format(
                len(self._data_points), self._kafka_topic))

            self._data_points = []
            self._consumer.commit()
        except Exception as ex:
            if "partial write: points beyond retention policy dropped" in str(ex):
                LOG.warning("Some points older than retention policy were dropped")
                self._data_points = []
                self._consumer.commit()

            elif cfg.CONF.repositories.ignore_parse_point_error \
                    and "unable to parse" in str(ex):
                LOG.warning("Some points were unable to be parsed and were dropped")
                self._data_points = []
                self._consumer.commit()

            else:
                LOG.exception("Error writing to database: {}"
                              .format(self._data_points))
                self._data_points = []
                self._consumer.commit()
                raise ex

    def run(self):
        print("enter run method:")
        LOG.info("enter run method:")
        try:
            for raw_message in self._consumer:
                try:
                    print(raw_message)
                    LOG.info("raw_messages:")
                    LOG.info(raw_message)
                    message = raw_message
                    print("enter")
                    data_point = self.repository.process_message(message)
                    self._data_points.append(data_point)
                except Exception:
                    LOG.exception('Error processing message. Message is '
                                  'being dropped. {}'.format(message))

                if len(self._data_points) >= self._batch_size:
                    self._flush()
        except Exception:
            LOG.exception(
                'Persister encountered fatal exception processing '
                'messages. '
                'Shutting down all threads and exiting')
            os._exit(1)
